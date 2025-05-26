# -*- coding: utf-8 -*-

import pibooth
from pibooth.utils import LOGGER


class PrinterPlugin(object):

    """Plugin to manage the printer.
    """

    name = 'pibooth-core:printer'

    def __init__(self, plugin_manager):
        self._pm = plugin_manager

    def print_picture(self, cfg, win, app):
        # Vérification de l’état de l’imprimante Selphy
        error_msg = self._check_selphy_status(app)
        if error_msg:
            LOGGER.error("⛔ Impression annulée : %s", error_msg)
            self._display_error(win, error_msg)
            return  # On ne lance pas l’impression

        LOGGER.info("✅ Envoi de la photo à l’imprimante")
        app.printer.print_file(app.previous_picture_file,
                            cfg.getint('PRINTER', 'pictures_per_page'))
        app.count.printed += 1
        app.count.remaining_duplicates -= 1


    @pibooth.hookimpl
    def pibooth_cleanup(self, app):
        app.printer.quit()

    @pibooth.hookimpl
    def state_failsafe_enter(self, cfg, app):
        """Reset variables set in this plugin.
        """
        app.count.remaining_duplicates = cfg.getint('PRINTER', 'max_duplicates')

    @pibooth.hookimpl
    def state_wait_do(self, cfg, app, win, events):
        if app.find_print_event(events) and app.previous_picture_file and app.printer.is_installed():

            if app.count.remaining_duplicates <= 0:
                LOGGER.warning("Too many duplicates sent to the printer (%s max)",
                               cfg.getint('PRINTER', 'max_duplicates'))
                return

            elif not app.printer.is_ready():
                LOGGER.warning("Maximum number of printed pages reached (%s/%s max)", app.count.printed,
                               cfg.getint('PRINTER', 'max_pages'))
                return

            self.print_picture(cfg, win, app)

    @pibooth.hookimpl
    def state_processing_enter(self, cfg, app):
        app.count.remaining_duplicates = cfg.getint('PRINTER', 'max_duplicates')

    @pibooth.hookimpl
    def state_processing_do(self, cfg, win, app):
        if app.previous_picture_file and app.printer.is_ready():
            number = cfg.gettyped('PRINTER', 'auto_print')
            if number == 'max':
                number = cfg.getint('PRINTER', 'max_duplicates')
            for i in range(number):
                if app.count.remaining_duplicates > 0:
                    self.print_picture(cfg, win, app)

    @pibooth.hookimpl
    def state_print_do(self, cfg, app, win, events):
        if app.find_print_event(events) and app.previous_picture_file:
            self.print_picture(cfg, win, app)

    def _check_selphy_status(self, app):
        try:
            import cups
            conn = cups.Connection()
            LOGGER.info(conn.getPrinters().items())
            for name, attrs in conn.getPrinters().items():
                if "SELPHY" in name.upper():
                    reasons = [r.lower() for r in attrs.get("printer-state-reasons", [])]

                    LOGGER.info("Vérification de l'état de l'imprimante %s", name)
                    LOGGER.info(reasons)

                    if any("offline" in r for r in reasons):
                        return "Imprimante déconnectée"
                    if any("media-empty" in r for r in reasons):
                        return "Plus de papier"
                    if any("marker-supply-empty" in r for r in reasons):
                        return "Cartouche vide"
                    if any("input-tray-missing" in r for r in reasons):
                        return "Pas de papier ou cassette mal insérée"

            return None  # tout est bon
        except Exception as e:
            LOGGER.exception("Erreur CUPS lors de la vérification d'imprimante")
            return "Erreur de communication avec l’imprimante"

    def _display_error(self, win, message):
        win.show_oops()
        import pygame
        import time

        font = pygame.font.Font(None, 48)
        win.surface.fill((0, 0, 0))
        text_surface = font.render(message, True, (255, 0, 0))
        rect = text_surface.get_rect(center=win.surface.get_rect().center)
        win.surface.blit(text_surface, rect)
        pygame.display.update()
        time.sleep(3)  # ✅ Garde l'écran figé 3 secondes

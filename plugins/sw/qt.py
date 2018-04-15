import threading

from PyQt5.Qt import QInputDialog, QLineEdit, QVBoxLayout, QLabel

from electrum.i18n import _
from electrum.plugins import hook
from electrum.wallet import Standard_Wallet
from .sw import SwPlugin
from ..hw_wallet.qt import QtHandlerBase, QtPluginBase
from electrum_gui.qt.util import *

#from btchip.btchipPersoWizard import StartBTChipPersoDialog

class Plugin(SwPlugin, QtPluginBase):
    icon_unpaired = ":icons/sw_unpaired.png"
    icon_paired = ":icons/sw_paired.png"

    def create_handler(self, window):
        return Sw_Handler(window)

    # @hook
    # def receive_menu(self, menu, addrs, wallet):
    #    if type(wallet) is not Standard_Wallet:
    #        return
    #    keystore = wallet.get_keystore()
    #    if type(keystore) == self.keystore_class and len(addrs) == 1:
    #        def show_address():
    #            keystore.thread.add(partial(self.show_address, wallet, addrs[0]))
    #        menu.addAction(_("Show on Sw"), show_address)

class Sw_Handler(QtHandlerBase):
    # setup_signal = pyqtSignal()
    auth_signal = pyqtSignal(object)

    def __init__(self, win):
        super(Sw_Handler, self).__init__(win, 'SW')
        # self.setup_signal.connect(self.setup_dialog)
        self.auth_signal.connect(self.auth_dialog)

    def word_dialog(self, msg):
        response = QInputDialog.getText(self.top_level_window(), "Smart Wallet Authentication", msg, QLineEdit.Password)
        if not response[1]:
            self.word = None
        else:
            self.word = str(response[0])
        self.done.set()
        
    def message_dialog(self, msg):
        self.clear_dialog()
        self.dialog = dialog = WindowModalDialog(self.top_level_window(), _("SW Status"))
        l = QLabel(msg)
        vbox = QVBoxLayout(dialog)
        vbox.addWidget(l)
        dialog.show()

    def auth_dialog(self, data):
        try:
            from .auth2fa import LedgerAuthDialog
        except ImportError as e:
            self.message_dialog(str(e))
            return
        dialog = LedgerAuthDialog(self, data)
        dialog.exec_()
        self.word = dialog.pin
        self.done.set()

    def get_auth(self, data):
        self.done.clear()
        self.auth_signal.emit(data)
        self.done.wait()
        return self.word

        
        
        

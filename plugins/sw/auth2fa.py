from binascii import hexlify, unhexlify

from PyQt5.Qt import QDialog, QLineEdit, QTextEdit, QVBoxLayout, QLabel
import PyQt5.QtCore as QtCore
from PyQt5.QtWidgets import *

from electrum.i18n import _
from electrum_gui.qt.util import *
from electrum.util import print_msg

import os, hashlib, logging, json, copy
from electrum_gui.qt.qrcodewidget import QRCodeWidget
from btchip.btchip import *

DEBUG = False

helpTxt = [_("Your Ledger Wallet wants to tell you a one-time PIN code.<br><br>" \
            "For best security you should unplug your device, open a text editor on another computer, " \
            "put your cursor into it, and plug your device into that computer. " \
            "It will output a summary of the transaction being signed and a one-time PIN.<br><br>" \
            "Verify the transaction summary and type the PIN code here.<br><br>" \
            "Before pressing enter, plug the device back into this computer.<br>" ),
        _("Verify the address below.<br>Type the character from your security card corresponding to the <u><b>BOLD</b></u> character."),
        _("Waiting for authentication on your mobile phone"),
        _("Transaction accepted by mobile phone. Waiting for confirmation."),
        _("Click Pair button to begin pairing a mobile phone."),
        _("Scan this QR code with your LedgerWallet phone app to pair it with this Ledger device.<br>" 
            "To complete pairing you will need your security card to answer a challenge." )
        ]

class LedgerAuthDialog(QDialog):
    def __init__(self, handler, data):
        '''Ask user for 2nd factor authentication. Support text, security card and paired mobile methods.
        Use last method from settings, but support new pairing and downgrade.
        '''
        QDialog.__init__(self, handler.top_level_window())
        self.handler = handler
        self.txdata = data
        self.idxs = self.txdata['keycardData'] if self.txdata['confirmationType'] > 1 else ''
        self.setMinimumWidth(600)
        self.setWindowTitle(_("Ledger Wallet Authentication"))
        self.cfg = copy.deepcopy(self.handler.win.wallet.get_keystore().cfg)
        self.dongle = self.handler.win.wallet.get_keystore().get_client().dongle
        self.ws = None
        self.pin = ''
        
        self.devmode = self.getDevice2FAMode()
        if self.devmode == 0x11 or self.txdata['confirmationType'] == 1:
            self.cfg['mode'] = 0
        
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        
        def on_change_mode(idx):
            if idx < 2 and self.ws:
                self.ws.stop()
                self.ws = None
            self.cfg['mode'] = 0 if self.devmode == 0x11 else idx if idx > 0 else 1
            if self.cfg['mode'] > 1 and self.cfg['pair'] and not self.ws:
                self.req_validation()
            if self.cfg['mode'] > 0:
                self.handler.win.wallet.get_keystore().cfg = self.cfg
                self.handler.win.wallet.save_keystore()
            self.update_dlg()
        def add_pairing():
            self.do_pairing()
        def return_pin():
            self.pin = self.pintxt.text() if self.txdata['confirmationType'] == 1 else self.cardtxt.text() 
            if self.cfg['mode'] == 1:
                self.pin = ''.join(chr(int(str(i),16)) for i in self.pin)
            self.accept()
        
        self.modebox = QWidget()
        modelayout = QHBoxLayout()
        self.modebox.setLayout(modelayout)
        modelayout.addWidget(QLabel(_("Method:")))
        self.modes = QComboBox()
        modelayout.addWidget(self.modes, 2)
        self.addPair = QPushButton(_("Pair"))
        self.addPair.setMaximumWidth(60)
        modelayout.addWidget(self.addPair)
        modelayout.addStretch(1)
        self.modebox.setMaximumHeight(50)
        vbox.addWidget(self.modebox)
        
        self.populate_modes()
        self.modes.currentIndexChanged.connect(on_change_mode)
        self.addPair.clicked.connect(add_pairing)
        
        self.helpmsg = QTextEdit()
        self.helpmsg.setStyleSheet("QTextEdit { background-color: lightgray; }")
        self.helpmsg.setReadOnly(True)
        vbox.addWidget(self.helpmsg)
        
        self.pinbox = QWidget()
        pinlayout = QHBoxLayout()
        self.pinbox.setLayout(pinlayout)
        self.pintxt = QLineEdit()
        self.pintxt.setEchoMode(2)
        self.pintxt.setMaxLength(4)
        self.pintxt.returnPressed.connect(return_pin)
        pinlayout.addWidget(QLabel(_("Enter PIN:")))
        pinlayout.addWidget(self.pintxt)
        pinlayout.addWidget(QLabel(_("NOT DEVICE PIN - see above")))
        pinlayout.addStretch(1)
        self.pinbox.setVisible(self.cfg['mode'] == 0)
        vbox.addWidget(self.pinbox)
                    
        self.cardbox = QWidget()
        card = QVBoxLayout()
        self.cardbox.setLayout(card)
        self.addrtext = QTextEdit()
        self.addrtext.setStyleSheet("QTextEdit { color:blue; background-color:lightgray; padding:15px 10px; border:none; font-size:20pt; }")
        self.addrtext.setReadOnly(True)
        self.addrtext.setMaximumHeight(120)
        card.addWidget(self.addrtext)
        
        def pin_changed(s):
            if len(s) < len(self.idxs):
                i = self.idxs[len(s)]
                addr = self.txdata['address']
                addr = addr[:i] + '<u><b>' + addr[i:i+1] + '</u></b>' + addr[i+1:]
                self.addrtext.setHtml(str(addr))
            else:
                self.addrtext.setHtml(_("Press Enter"))
                
        pin_changed('')    
        cardpin = QHBoxLayout()
        cardpin.addWidget(QLabel(_("Enter PIN:")))
        self.cardtxt = QLineEdit()
        self.cardtxt.setEchoMode(2)
        self.cardtxt.setMaxLength(len(self.idxs))
        self.cardtxt.textChanged.connect(pin_changed)
        self.cardtxt.returnPressed.connect(return_pin)
        cardpin.addWidget(self.cardtxt)
        cardpin.addWidget(QLabel(_("NOT DEVICE PIN - see above")))
        cardpin.addStretch(1)
        card.addLayout(cardpin)
        self.cardbox.setVisible(self.cfg['mode'] == 1)
        vbox.addWidget(self.cardbox)
        
        self.pairbox = QWidget()
        pairlayout = QVBoxLayout()
        self.pairbox.setLayout(pairlayout)
        pairhelp = QTextEdit(helpTxt[5])
        pairhelp.setStyleSheet("QTextEdit { background-color: lightgray; }")
        pairhelp.setReadOnly(True)
        pairlayout.addWidget(pairhelp, 1)
        self.pairqr = QRCodeWidget()
        pairlayout.addWidget(self.pairqr, 4)
        self.pairbox.setVisible(False)
        vbox.addWidget(self.pairbox)
        self.update_dlg()
        
        if self.cfg['mode'] > 1 and not self.ws:
            self.req_validation()
        
    def populate_modes(self):
        self.modes.blockSignals(True)
        self.modes.clear()
        self.modes.addItem(_("Summary Text PIN (requires dongle replugging)") if self.txdata['confirmationType'] == 1 else _("Summary Text PIN is Disabled"))
        if self.txdata['confirmationType'] > 1:
            self.modes.addItem(_("Security Card Challenge"))
            if not self.cfg['pair']:
                self.modes.addItem(_("Mobile - Not paired")) 
            else:
                self.modes.addItem(_("Mobile - {}").format(self.cfg['pair'][1]))
        self.modes.blockSignals(False)
        
    def update_dlg(self):
        self.modes.setCurrentIndex(self.cfg['mode'])
        self.modebox.setVisible(True)
        self.addPair.setText(_("Pair") if not self.cfg['pair'] else _("Re-Pair"))
        self.addPair.setVisible(self.txdata['confirmationType'] > 2)
        self.helpmsg.setText(helpTxt[self.cfg['mode'] if self.cfg['mode'] < 2 else 2 if self.cfg['pair'] else 4])
        self.helpmsg.setMinimumHeight(180 if self.txdata['confirmationType'] == 1 else 100)
        self.pairbox.setVisible(False)
        self.helpmsg.setVisible(True)
        self.pinbox.setVisible(self.cfg['mode'] == 0)
        self.cardbox.setVisible(self.cfg['mode'] == 1)
        self.pintxt.setFocus(True) if self.cfg['mode'] == 0 else self.cardtxt.setFocus(True)
        self.setMaximumHeight(200)
        
    def getDevice2FAMode(self):
        apdu = [0xe0, 0x24, 0x01, 0x00, 0x00, 0x01] # get 2fa mode
        try:
            mode = self.dongle.exchange( bytearray(apdu) )
            return mode
        except BTChipException as e:
            debug_msg('Device getMode Failed')
        return 0x11
    
    def closeEvent(self, evnt):
        debug_msg("CLOSE - Stop WS")
        if self.ws:
            self.ws.stop()
        if self.pairbox.isVisible():
            evnt.ignore()
            self.update_dlg()


def debug_msg(*args):
    if DEBUG:
        print_msg(*args)        

    
        
        
        

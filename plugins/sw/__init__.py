from electrum.i18n import _

fullname = 'Smart Wallet'
description = 'Provides support for SW hardware wallet'
requires = [('btchip', 'github.com/ledgerhq/btchip-python')]
registers_keystore = ('hardware', 'sw', _("Smart Wallet"))
available_for = ['qt', 'cmdline']

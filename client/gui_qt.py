import sys, time, datetime, re

# todo: see PySide

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.QtCore as QtCore
import PyQt4.QtGui as QtGui

from wallet import format_satoshis
from decimal import Decimal






class Sender(QtCore.QThread):
    def run(self):
        while True:
            self.emit(QtCore.SIGNAL('testsignal'))
            time.sleep(0.5)

class StatusBarButton(QPushButton):
    def __init__(self, icon, tooltip, func):
        QPushButton.__init__(self, icon, '')
        self.setToolTip(tooltip)
        self.setFlat(True)
        self.setMaximumWidth(25)
        self.clicked.connect(func)
        self.func = func

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Return:
            apply(self.func,())


def ok_cancel_buttons(dialog):
    hbox = QHBoxLayout()
    hbox.addStretch(1)
    b = QPushButton("OK")
    hbox.addWidget(b)
    b.clicked.connect(dialog.accept)
    b = QPushButton("Cancel")
    hbox.addWidget(b)
    b.clicked.connect(dialog.reject)
    return hbox


class ElectrumWindow(QMainWindow):

    def __init__(self, wallet):
        QMainWindow.__init__(self)
        self.wallet = wallet

        self.tabs = tabs = QTabWidget(self)
        tabs.addTab(self.create_history_tab(), 'History')
        tabs.addTab(self.create_send_tab(),    'Send')
        tabs.addTab(self.create_receive_tab(), 'Receive')
        tabs.addTab(self.create_contacts_tab(),'Contacts')
        tabs.addTab(self.create_wall_tab(),    'Wall')
        tabs.setMinimumSize(600, 400)
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(tabs)
        self.create_status_bar()
        self.setGeometry(100,100,840,400)
        self.setWindowTitle( 'Electrum ' + self.wallet.electrum_version )
        self.show()

        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        QShortcut(QKeySequence("Ctrl+PgUp"), self, lambda: tabs.setCurrentIndex( (tabs.currentIndex() - 1 )%tabs.count() ))
        QShortcut(QKeySequence("Ctrl+PgDown"), self, lambda: tabs.setCurrentIndex( (tabs.currentIndex() + 1 )%tabs.count() ))



    def connect_slots(self, sender):
        self.connect(sender, QtCore.SIGNAL('testsignal'), self.update_wallet)


    def update_wallet(self):
        if self.wallet.interface.is_connected:
            if self.wallet.interface.blocks == 0:
                text = "Server not ready"
                icon = QIcon("icons/status_disconnected.png")
            elif not self.wallet.interface.was_polled:
                text = "Synchronizing..."
                icon = QIcon("icons/status_waiting.svg")
            else:
                c, u = self.wallet.get_balance()
                text =  "Balance: %s "%( format_satoshis(c) )
                if u: text +=  "[%s unconfirmed]"%( format_satoshis(u,True) )
                icon = QIcon("icons/status_connected.png")
        else:
            text = "Not connected"
            icon = QIcon("icons/status_disconnected.png")

        self.statusBar().showMessage(text)
        self.status_button.setIcon( icon )

        if self.wallet.interface.was_updated:
            self.wallet.interface.was_updated = False
            self.textbox.setText( self.wallet.interface.message )
            self.update_history_tab()
            self.update_receive_tab()
            self.update_contacts_tab()


    def create_history_tab(self):
        self.history_list = w = QTreeWidget(self)
        #print w.getContentsMargins()
        w.setColumnCount(5)
        w.setColumnWidth(0, 40) 
        w.setColumnWidth(1, 140) 
        w.setColumnWidth(2, 350) 
        w.setColumnWidth(3, 140) 
        w.setColumnWidth(4, 140) 
        w.setHeaderLabels( [ '', 'Date', 'Description', 'Amount', 'Balance'] )
        self.connect(w, SIGNAL('itemActivated(QTreeWidgetItem*, int)'), self.tx_details)
        self.connect(w, SIGNAL('itemDoubleClicked(QTreeWidgetItem*, int)'), self.tx_label_clicked)
        self.connect(w, SIGNAL('itemChanged(QTreeWidgetItem*, int)'), self.tx_label_changed)
        return w

    def tx_details(self, item, column):
        tx_hash = str(item.toolTip(0))
        tx = self.wallet.tx_history.get(tx_hash)

        if tx['height']:
            conf = self.wallet.interface.blocks - tx['height'] + 1
            time_str = datetime.datetime.fromtimestamp( tx['nTime']).isoformat(' ')[:-3]
        else:
            conf = 0
            time_str = 'pending'

        tx_details = "Transaction Details:\n\n" \
            + "Transaction ID:\n" + tx_hash + "\n\n" \
            + "Status: %d confirmations\n\n"%conf  \
            + "Date: %s\n\n"%time_str \
            + "Inputs:\n-"+ '\n-'.join(tx['inputs']) + "\n\n" \
            + "Outputs:\n-"+ '\n-'.join(tx['outputs'])

        r = self.wallet.receipts.get(tx_hash)
        if r:
            tx_details += "\n_______________________________________" \
                + '\n\nSigned URI: ' + r[2] \
                + "\n\nSigned by: " + r[0] \
                + '\n\nSignature: ' + r[1]

        QMessageBox.information(self, 'Details', tx_details, 'OK')


    def tx_label_clicked(self, item, column):
        if column==2 and item.isSelected():
            tx_hash = str(item.toolTip(0))
            self.is_edit=True
            #if not self.wallet.labels.get(tx_hash): item.setText(2,'')
            item.setFlags(Qt.ItemIsEditable|Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
            self.history_list.editItem( item, column )
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
            self.is_edit=False

    def tx_label_changed(self, item, column):
        if self.is_edit: 
            return
        self.is_edit=True
        tx_hash = str(item.toolTip(0))
        tx = self.wallet.tx_history.get(tx_hash)
        s = self.wallet.labels.get(tx_hash)
        text = str( item.text(2) )
        if text: 
            self.wallet.labels[tx_hash] = text
            item.setForeground(2, QBrush(QColor('black')))
        else:
            if s: self.wallet.labels.pop(tx_hash)
            text = tx['default_label']
            item.setText(2, text)
            item.setForeground(2, QBrush(QColor('gray')))
        self.is_edit=False

    def address_label_clicked(self, item, column, l):
        if column==1 and item.isSelected():
            item.setFlags(Qt.ItemIsEditable|Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
            l.editItem( item, column )
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)

    def address_label_changed(self, item, column, l):
        addr = str(item.text(0))
        text = str( item.text(1) )
        if text:
            self.wallet.labels[addr] = text
        else:
            s = self.wallet.labels.get(addr)
            if s: self.wallet.labels.pop(addr)
        self.update_history_tab()

    def update_history_tab(self):
        self.history_list.clear()
        balance = 0
        for tx in self.wallet.get_tx_history():
            tx_hash = tx['tx_hash']
            if tx['height']:
                conf = self.wallet.interface.blocks - tx['height'] + 1
                time_str = datetime.datetime.fromtimestamp( tx['nTime']).isoformat(' ')[:-3]
                icon = QIcon("icons/confirmed.png")
            else:
                conf = 0
                time_str = 'pending'
                icon = QIcon("icons/unconfirmed.svg")
            v = tx['value']
            balance += v 
            label = self.wallet.labels.get(tx_hash)
            is_default_label = (label == '') or (label is None)
            if is_default_label: label = tx['default_label']

            item = QTreeWidgetItem( [ '', time_str, label, format_satoshis(v,True), format_satoshis(balance)] )
            item.setFont(2, QFont('monospace'))
            item.setFont(3, QFont('monospace'))
            item.setFont(4, QFont('monospace'))
            item.setToolTip(0, tx_hash)
            if is_default_label:
                item.setForeground(2, QBrush(QColor('grey')))

            item.setIcon(0, icon)
            self.history_list.insertTopLevelItem(0,item)


    def create_send_tab(self):
        w = QWidget()

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(3,300)
        grid.setColumnStretch(4,1)

        self.payto_entry = paytoEdit = QLineEdit()
        grid.addWidget(QLabel('Pay to'), 1, 0)
        grid.addWidget(paytoEdit, 1, 1, 1, 3)

        descriptionEdit = QLineEdit()
        grid.addWidget(QLabel('Description'), 2, 0)
        grid.addWidget(descriptionEdit, 2, 1, 1, 3)

        amountEdit = QLineEdit()
        grid.addWidget(QLabel('Amount'), 3, 0)
        grid.addWidget(amountEdit, 3, 1, 1, 2)
        
        feeEdit = QLineEdit()
        grid.addWidget(QLabel('Fee'), 4, 0)
        grid.addWidget(feeEdit, 4, 1, 1, 2)
        
        b = QPushButton("Send")
        b.clicked.connect( lambda: self.do_send(paytoEdit,descriptionEdit,amountEdit,feeEdit ) )
        grid.addWidget(b, 5, 1)

        b = QPushButton("Clear")
        b.clicked.connect( lambda: map( lambda x: x.setText(''), [paytoEdit,descriptionEdit,amountEdit,feeEdit] ) )
        grid.addWidget(b, 5, 2)

        w.setLayout(grid) 
        w.show()

        w2 = QWidget()
        vbox = QVBoxLayout()
        vbox.addWidget(w)
        vbox.addStretch(1)
        w2.setLayout(vbox)

        return w2

    def do_send(self, payto_entry, label_entry, amount_entry, fee_entry):

        label = str( label_entry.text() )
        r = str( payto_entry.text() )
        r = r.strip()

        m1 = re.match('^(|([\w\-\.]+)@)((\w[\w\-]+\.)+[\w\-]+)$', r)
        m2 = re.match('(|([\w\-\.]+)@)((\w[\w\-]+\.)+[\w\-]+) \<([1-9A-HJ-NP-Za-km-z]{26,})\>', r)
        
        if m1:
            to_address = self.wallet.get_alias(r, True, self.show_message, self.question)
            if not to_address:
                return
        elif m2:
            to_address = m2.group(5)
        else:
            to_address = r

        if not self.wallet.is_valid(to_address):
            QMessageBox.warning(self, 'Error', 'Invalid Bitcoin Address:\n'+to_address, 'OK')
            return

        try:
            amount = int( Decimal( str( amount_entry.text())) * 100000000 )
        except:
            QMessageBox.warning(self, 'Error', 'Invalid Amount', 'OK')
            return
        try:
            fee = int( Decimal( str( fee_entry.text())) * 100000000 )
        except:
            QMessageBox.warning(self, 'Error', 'Invalid Fee', 'OK')
            return

        if self.wallet.use_encryption:
            password = self.password_dialog()
            if not password:
                return
        else:
            password = None

        try:
            tx = self.wallet.mktx( to_address, amount, label, password, fee )
        except BaseException, e:
            self.show_message(e.message)
            return
            
        status, msg = self.wallet.sendtx( tx )
        if status:
            QMessageBox.information(self, '', 'Payment sent.\n'+msg, 'OK')
            payto_entry.setText("")
            label_entry.setText("")
            amount_entry.setText("")
            fee_entry.setText("")
            self.update_contacts_tab()
        else:
            QMessageBox.warning(self, 'Error', msg, 'OK')




    def make_address_list(self, is_recv):

        l = QTreeWidget(self)
        l.setColumnCount(3)
        l.setColumnWidth(0, 350) 
        l.setColumnWidth(1, 330)
        l.setColumnWidth(2, 20) 
        l.setHeaderLabels( ['Address', 'Label','Tx'])

        vbox = QVBoxLayout()
        vbox.setMargin(0)
        vbox.setSpacing(0)
        vbox.addWidget(l)

        hbox = QHBoxLayout()
        hbox.setMargin(0)
        hbox.setSpacing(0)
        qrButton = QPushButton("QR")
        copyButton = QPushButton("Copy to Clipboard")
        def copy2clipboard(l):
            i = l.currentItem()
            if not i: return
            addr = str( i.text(0) )
            self.app.clipboard().setText(addr)

        copyButton.clicked.connect(lambda: copy2clipboard(l))
        hbox.addWidget(qrButton)
        hbox.addWidget(copyButton)
        if not is_recv:
            addButton = QPushButton("New")
            addButton.clicked.connect(self.newaddress_dialog)
            hbox.addWidget(addButton)
            paytoButton = QPushButton('Pay to')
            def payto(l):
                i = l.currentItem()
                if not i: return
                addr = str( i.text(0) )
                self.tabs.setCurrentIndex(1)
                self.payto_entry.setText(addr)
            paytoButton.clicked.connect(lambda : payto(l))
            hbox.addWidget(paytoButton)
        hbox.addStretch(1)
        buttons = QWidget()
        buttons.setLayout(hbox)
        vbox.addWidget(buttons)

        w = QWidget()
        w.setLayout(vbox)
        return w, l

    def create_receive_tab(self):
        w, l = self.make_address_list(True)
        self.connect(l, SIGNAL('itemDoubleClicked(QTreeWidgetItem*, int)'), lambda a, b: self.address_label_clicked(a,b,l))
        self.connect(l, SIGNAL('itemChanged(QTreeWidgetItem*, int)'), lambda a,b: self.address_label_changed(a,b,l))
        self.receive_list = l
        return w

    def create_contacts_tab(self):
        w, l = self.make_address_list(False)
        self.connect(l, SIGNAL('itemDoubleClicked(QTreeWidgetItem*, int)'), lambda a, b: self.address_label_clicked(a,b,l))
        self.connect(l, SIGNAL('itemChanged(QTreeWidgetItem*, int)'), lambda a,b: self.address_label_changed(a,b,l))
        self.connect(l, SIGNAL('itemActivated(QTreeWidgetItem*, int)'), self.show_contact_details)
        self.contacts_list = l
        return w

    def update_receive_tab(self):
        self.receive_list.clear()
        for address in self.wallet.all_addresses():
            if self.wallet.is_change(address):continue
            label = self.wallet.labels.get(address,'')
            n = 0 
            h = self.wallet.history.get(address,[])
            for item in h:
                if not item['is_in'] : n=n+1
            tx = "None" if n==0 else "%d"%n
            item = QTreeWidgetItem( [ address, label, tx] )
            item.setFont(0, QFont('monospace'))
            self.receive_list.addTopLevelItem(item)

    def show_contact_details(self, item, column):
        m = str(item.text(0))
        a = self.wallet.aliases.get(m)
        if a:
            if a[0] in self.wallet.authorities.keys():
                s = self.wallet.authorities.get(a[0])
            else:
                s = "self-signed"
            msg = 'Alias: '+ m + '\nTarget address: '+ a[1] + '\n\nSigned by: ' + s + '\nSigning address:' + a[0]
            QMessageBox.information(self, 'Alias', msg, 'OK')

    def update_contacts_tab(self):
        self.contacts_list.clear()
        for alias, v in self.wallet.aliases.items():
            s, target = v
            label = self.wallet.labels.get(alias,'')
            item = QTreeWidgetItem( [ alias, label, '-'] )
            self.contacts_list.addTopLevelItem(item)
            
        for address in self.wallet.addressbook:
            label = self.wallet.labels.get(address,'')
            n = 0 
            for item in self.wallet.tx_history.values():
                if address in item['outputs'] : n=n+1
            tx = "None" if n==0 else "%d"%n
            item = QTreeWidgetItem( [ address, label, tx] )
            item.setFont(0, QFont('monospace'))
            self.contacts_list.addTopLevelItem(item)


    def create_wall_tab(self):
        self.textbox = textbox = QTextEdit(self)
        textbox.setReadOnly(True)
        return textbox

    def create_status_bar(self):
        sb = QStatusBar()
        sb.setFixedHeight(35)
        sb.addPermanentWidget( StatusBarButton( QIcon("icons/lock.svg"), "Password", lambda: self.change_password_dialog(self.wallet, self) ) )
        sb.addPermanentWidget( StatusBarButton( QIcon("icons/preferences.png"), "Preferences", self.settings_dialog ) )
        sb.addPermanentWidget( StatusBarButton( QIcon("icons/seed.png"), "Seed", lambda: self.show_seed_dialog(self.wallet, self) ) )
        self.status_button = StatusBarButton( QIcon("icons/status_disconnected.png"), "Network", lambda: self.network_dialog(self.wallet, self) ) 
        sb.addPermanentWidget( self.status_button )
        self.setStatusBar(sb)

    def newaddress_dialog(self):

        text, ok = QInputDialog.getText(self, 'New Contact', 'Address:')
        address = str(text)
        if ok:
            if self.wallet.is_valid(address):
                self.wallet.addressbook.append(address)
                self.wallet.save()
                self.update_contacts_tab()
            else:
                QMessageBox.warning(self, 'Error', 'Invalid Address', 'OK')

    @staticmethod
    def show_seed_dialog(wallet, parent=None):
        import mnemonic
        if wallet.use_encryption:
            password = self.password_dialog()
            if not password: return
        else:
            password = None
            
        try:
            seed = wallet.pw_decode( wallet.seed, password)
        except:
            QMessageBox.warning(parent, 'Error', 'Invalid Password', 'OK')
            return

        msg = "Your wallet generation seed is:\n\n" + seed \
              + "\n\nPlease keep it in a safe place; if you lose it, you will not be able to restore your wallet.\n\n" \
              + "Equivalently, your wallet seed can be stored and recovered with the following mnemonic code:\n\n\"" \
              + ' '.join(mnemonic.mn_encode(seed)) + "\""

        QMessageBox.information(parent, 'Seed', msg, 'OK')

    def question(self, msg):
        return QMessageBox.question(self, 'Message', msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

    def show_message(self, msg):
        QMessageBox.information(self, 'Message', msg, 'OK')

    @staticmethod
    def password_dialog( parent=None ):
        d = QDialog(parent)
        d.setModal(1)

        pw = QLineEdit()
        pw.setEchoMode(2)

        vbox = QVBoxLayout()
        msg = 'Please enter your password'
        vbox.addWidget(QLabel(msg))

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel('Password'), 1, 0)
        grid.addWidget(pw, 1, 1)
        vbox.addLayout(grid)

        vbox.addLayout(ok_cancel_buttons(d))
        d.setLayout(vbox) 

        if not d.exec_(): return
        return str(pw.text())

    @staticmethod
    def change_password_dialog( wallet, parent=None ):
        d = QDialog(parent)
        d.setModal(1)

        pw = QLineEdit()
        pw.setEchoMode(2)
        new_pw = QLineEdit()
        new_pw.setEchoMode(2)
        conf_pw = QLineEdit()
        conf_pw.setEchoMode(2)

        vbox = QVBoxLayout()
        msg = 'Your wallet is encrypted. Use this dialog to change your password.\nTo disable wallet encryption, enter an empty new password.' if wallet.use_encryption else 'Your wallet keys are not encrypted'
        vbox.addWidget(QLabel(msg))

        grid = QGridLayout()
        grid.setSpacing(8)

        if wallet.use_encryption:
            grid.addWidget(QLabel('Password'), 1, 0)
            grid.addWidget(pw, 1, 1)

        grid.addWidget(QLabel('New Password'), 2, 0)
        grid.addWidget(new_pw, 2, 1)

        grid.addWidget(QLabel('Confirm Password'), 3, 0)
        grid.addWidget(conf_pw, 3, 1)
        vbox.addLayout(grid)

        vbox.addLayout(ok_cancel_buttons(d))
        d.setLayout(vbox) 

        if not d.exec_(): return

        password = str(pw.text()) if wallet.use_encryption else None
        new_password = str(new_pw.text())
        new_password2 = str(conf_pw.text())

        try:
            seed = wallet.pw_decode( wallet.seed, password)
        except:
            QMessageBox.warning(parent, 'Error', 'Incorrect Password', 'OK')
            return

        if new_password != new_password2:
            QMessageBox.warning(parent, 'Error', 'Passwords do not match', 'OK')
            return

        wallet.update_password(seed, new_password)

    @staticmethod
    def seed_dialog(wallet, parent=None):
        d = QDialog(parent)
        d.setModal(1)

        vbox = QVBoxLayout()
        msg = "Please enter your wallet seed or the corresponding mnemonic list of words, and the gap limit of your wallet."
        vbox.addWidget(QLabel(msg))

        grid = QGridLayout()
        grid.setSpacing(8)

        seed_e = QLineEdit()
        grid.addWidget(QLabel('Seed or mnemonic'), 1, 0)
        grid.addWidget(seed_e, 1, 1)

        gap_e = QLineEdit()
        gap_e.setText("5")
        grid.addWidget(QLabel('Gap limit'), 2, 0)
        grid.addWidget(gap_e, 2, 1)

        vbox.addLayout(grid)

        vbox.addLayout(ok_cancel_buttons(d))
        d.setLayout(vbox) 

        if not d.exec_(): return

        try:
            gap = int(str(gap_e.text()))
        except:
            show_message("error")
            sys.exit(1)

        try:
            seed = str(seed_e.text())
            seed.decode('hex')
        except:
            import mnemonic
            print "not hex, trying decode"
            seed = mnemonic.mn_decode( seed.split(' ') )
        if not seed:
            show_message("no seed")
            sys.exit(1)
        
        wallet.seed = seed
        wallet.gap_limit = gap
        return True


    def settings_dialog(self):
        d = QDialog(self)
        d.setModal(1)

        vbox = QVBoxLayout()

        msg = 'Here are the settings of your wallet'
        vbox.addWidget(QLabel(msg))

        grid = QGridLayout()
        grid.setSpacing(8)

        fee_line = QLineEdit()
        fee_line.setText("%s"% str( Decimal( self.wallet.fee)/100000000 ) )
        grid.addWidget(QLabel('Fee'), 2, 0)
        grid.addWidget(fee_line, 2, 1)
        vbox.addLayout(grid)

        vbox.addLayout(ok_cancel_buttons(d))
        d.setLayout(vbox) 

        if not d.exec_(): return

        fee = str(fee_line.text())
        try:
            fee = int( 100000000 * Decimal(fee) )
        except:
            QMessageBox.warning(self, 'Error', 'Invalid value:%s'%fee, 'OK')
            return

        self.wallet.fee = fee
        self.wallet.save()

    @staticmethod 
    def network_dialog(wallet, parent=None):

        if True:
            if wallet.interface.is_connected:
                status = "Connected to %s.\n%d blocks\nresponse time: %f"%(wallet.interface.host, wallet.interface.blocks, wallet.interface.rtime)
            else:
                status = "Not connected"
            host = wallet.interface.host
            port = wallet.interface.port
        else:
            import random
            status = "Please choose a server."
            host = random.choice( wallet.interface.servers )
            port = 50000

        d = QDialog(parent)
        d.setModal(1)

        vbox = QVBoxLayout()
        vbox.addWidget(QLabel(status))

        grid = QGridLayout()
        grid.setSpacing(8)
        host_line = QLineEdit()
        host_line.setText("%s:%d"% (host,port) )
        grid.addWidget(QLabel('Server'), 2, 0)
        grid.addWidget(host_line, 2, 1)
        vbox.addLayout(grid)

        vbox.addLayout(ok_cancel_buttons(d))
        d.setLayout(vbox) 

        if not d.exec_(): return
        hh = str( host_line.text() )

        try:
            if ':' in hh:
                host, port = hh.split(':')
                port = int(port)
            else:
                host = hh
                port = 50000
        except:
            show_message("error")
            if parent == None:
                sys.exit(1)
            else:
                return

        wallet.interface.set_server(host, port) 
        return True




class ElectrumGui():

    def __init__(self, wallet):
        self.wallet = wallet
        self.app = QApplication(sys.argv)

    def restore_or_create(self):

        msg = "Wallet file not found.\nDo you want to create a new wallet,\n or to restore an existing one?"
        r = QMessageBox.question(None, 'Message', msg, 'create', 'restore', 'cancel', 0, 2)
        if r==2: return False
        
        is_recovery = (r==1)
        wallet = self.wallet
        if not is_recovery:
            wallet.new_seed(None)
            # ask for the server.
            ElectrumWindow.network_dialog(wallet)
            # generate first key
            wallet.synchronize()
            # run a dialog indicating the seed, ask the user to remember it
            ElectrumWindow.show_seed_dialog(wallet)
            #ask for password
            ElectrumWindow.change_password_dialog(wallet)
        else:
            # ask for the server.
            r = ElectrumWindow.network_dialog( wallet, parent=None )
            if not r: return False
            # ask for seed and gap.
            r = ElectrumWindow.seed_dialog( wallet )
            if not r: return False

            wallet.init_mpk( wallet.seed ) # not encrypted at this point
            wallet.synchronize()

            if wallet.is_found():
                # history and addressbook
                wallet.update_tx_history()
                wallet.fill_addressbook()
                print "recovery successful"
                wallet.save()
            else:
                QMessageBox.information(None, 'Message', "No transactions found for this seed", 'OK')

        wallet.save()
        return True



    def main(self):

        s = Sender()
        s.start()
        w = ElectrumWindow(self.wallet)
        w.app = self.app
        w.connect_slots(s)
        self.app.exec_()
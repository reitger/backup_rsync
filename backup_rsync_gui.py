#!/usr/bin/python3
# -*- coding: UTF-8 -*-
#
# 2022-2025, (c) by Ing. Gerald Reiter
# 1.0.0.1
#
# pylint: disable=C0103:invalid-name
# pylint: disable=C0209:consider-using-f-string
# pylint: disable=C0301:line-too-long
# pylint: disable=C0303:trailing-whitespace
# pylint: disable=W0231:super-init-not-called
# pylint: disable=W0401:wildcard-import
# pylint: disable=W0603:global-statement
# pylint: disable=W0614:unused-wildcard-import
# pylint: disable=W0718:broad-exception-caught
# pylint: disable=W1514:unspecified-encoding
# pylint: disable=R0902:too-many-instance-attributes
# pylint: disable=R0914:too-many-locals
# pylint: disable=R0915:too-many-statements
# pylint: disable=R0912:too-many-branches
# pylint: disable=R1732:consider-using-with
#
'''
Backup mit rsync:

* Arten von Backups:
Es kann zwischem Full-Backup und inkrementellem Backup gewählt 
werden. Beim inkrementellem Backup werden die in der Quelle nicht 
mehr vorhandenen Dateien vom Sicherungsverzeichnis ins ..._diff 
Verzeichnis verschoben. Das Sicherungsverzeichnis enthält den 
aktuellen Datenbestand, das ..._diff Verzeichnis die aktuell 
nicht mehr vorhandenen, gelöschten Dateien.


* Testlauf:
Es kann zum Überprüfen der erstellten Backup-Definition ein Testlauf 
durchgeführt werden, bei dem keine Daten geschrieben werden, sonder nur
protokolliert wird, was beim richtigen Backup mit rsync passieren würde. 
Im erzeugten Logfile im Backup-Zielverzeichnis kann das Ergebnis 
kontrolliert werden.


* Voraussetzung:
Im Hauptverzeichnis des Backup-Ziels (Backup-Basisverzeichnis) muss 
es ein 'backups' Verzeichnis geben, in dem das Backup gespeichert wird. 
Beispiel: 
Ein USB-Laufwerk mit Namen USB1TB ist unter '/media/ich' eingehängt, 
dann muss als Sicherungsziel '/media/ich/USB1TB/' angegeben werden.
Hier muss es ein Verzeichnis 'backups' geben, also '/media/ich/USB1TB/backups'.
Falls es nicht vorhanden ist, muss es manuell angelegt werden.
Wichtig: Unter "Beschreibung" dürfen keine Sonderzeichen außer äöüß und 
Leerzeichen eingegeben werden, da die Beschreibung als Teil des Ziel-Verzeichnisses
verwendet wird!


* Auswahl der Quelle:
Es kann ein beliebiger Pfad als Quelle ausgewählt werden, dazu kann man auch 
eine Liste von Verzeichnisname angegebenangeben, die ignoriert werden sollen, zB. 
'.Trash-1000' oder '.cache'. 
ACHTUNG: wenn nicht der ganze Pfad angegeben wird, wird alles unterhalb des Pfades,
der den Namen enthält, ignoriert. 
Beispiel: Bei Angabe von '.cache' also alle Unterverzeichnisse, die
unterhalb von ..../.cache liegen, und damit sowohl
/aaa/bbbb/.cache/... als auch aaa/ccc/ddd/.chache/...


* Dateistruktur im Backup-Ziel (lt. Beispiel-Konfiguration unten):
/media/ich/USB1TB/backups/MyWindowsDrive/ (a)
/media/ich/USB1TB/backups/Mein Windows Laufwerk_MyWindowsDrive.backupdef (b)
/media/ich/USB1TB/backups/Mein Windows Laufwerk_MyWindowsDrive.exclude (c)
/media/ich/USB1TB/backups/Mein Windows Laufwerk_MyWindowsDrive_[imestamp].log (d)
/media/ich/USB1TB/backups/Mein Windows Laufwerk_MyWindowsDrive/ (e)

(a) enthält alle Quelldateien, 
(b) enthält die Konfiguration dieses Backups,
(c) enthält die Liste alle zu ignorierenden Verzeichnisse,
(d) enthält das Logging lt. rsync,
(e) enthält bei inkrementellen Backups das Differenz-Verzeichnis dazu,

Die Verzeichnisnamen setzen sich aus Beschreibung ("section_label") und
Backup Name ("backup_name") der Konfiguration zusammen.
    

* Konfiguration:
Steuerung erfolgt über ein Konfig-File im JSON-Format. Es können in einer 
Konfigurationsdatei mehrere Backups definiert werden, die ausgewählt und
nacheinander ausgeführt werden.
Aufbau der JSDON-Datei:
Quellverzeichnisse als eine Liste von Dictionaries mit folgenden Schlüsselfeldern 
(Beispiel für user ich):
{
"backup_defs": [
    {
    "section_label": "Mein Windows Laufwerk",
    "source": "/home/ich/shares/meinNTFS-LW",
    "backup_destination_root": "/media/ich/USB1TB",
    "use_timestamp": "False",
    "backup_name": "MyWindowsDrive",
    "exclude_list": [
	    "*.lnk",
	    "?RECYCLE.BIN/",
	    "MSOCache/",
	    "System?Volume?Information/",
	    ".Trash-1000/",
	    "Software/"
        ]
    },
...
]
}
exclude_list enthält eine Liste aller zu ignorierenden Pfade/Dateien (siehe rsync)


* rsync-Flags im Log:
Bedeutung der Rsync log flags:

    First character:
        < - a file is being transferred to the remote (sent).
        > - a file is being transferred to the local (received).
        c - a local change/creation
        h - the item is a hard link
        . - the item is not being updated
        * - the rest is a message
    Second character:
        f - file
        d - directory
        L - symlink
        D - device
        S - special file
    Following letters:
        c - a different checksum
        s - size of a regular file is different
        t - modification time is different and is being updated to the sender's value
        T - that the modification time will be set to the transfer time
        p - permissions are different and are being updated to the sender's value
        o - the owner is different and is being updated to the sender's value
        g - the group is different and is being updated to the sender's value
        u - reserved for future use
        a - ACL information changed.
        x - extended attribute information changed.

(1) a newly created item replaces each letter with a "+"

(2) an identical item replaces the dots with spaces

(3) an unknown attribute replaces each letter with a "?"

'''
# --------------------------------------------


import os
import sys
import json
import re
import subprocess
import traceback
import time
import platform
import getpass
import tkinter as tk
from tkinter.scrolledtext import *
from tkinter import filedialog
from tkinter import messagebox

try:
    USE_PIL = 1
    from PIL import ImageTk, Image
except ImportError:
    USE_PIL = 0


logwindow = None
backupdefs = None
defdir = None
homedir = os.path.expanduser("~")
version = "1.0"
about_msg = '''Backup mit rsync

GUI für Backups beliebiger Verzeichnisse mit rsync
        
Version {0}

Copyright (c) 2025
Ing. Gerald Reiter
'''.format(version)



def writemsg(msg):
    '''Ausgabe im Log-Window'''
    print (msg)
    logwindow.insert(tk.END, msg)
    logwindow.see(tk.END)
    logwindow.master.update()


def load_backup_def(config_file):
    '''Konfiguration laden'''
    global backupdefs

    cfg = open(config_file, "r")
    jstxt = ""
    # Remove Commentlines starting with //
    while 1:
        zz = cfg.readline()
        if not zz:
            break
        zz = zz.lstrip()
        if not zz.startswith("//"):
            jstxt += zz
    cfg.close()
    #print(jstxt)
    try:
        backupdefs = json.loads(jstxt)
    except Exception as e:
        writemsg(jstxt)
        raise e


def save_backup_def(config_filename, backup_def):
    '''Save config'''
    cfgfile = open(config_filename, "w")
    cfgfile.write('''//# Config-File für Backups
//# Format: JSON
//# 
//# "backup_destination_root" ist üblicherweise der mountpoint für USB-Drives,
//# unter Linux-Mint: "/media/[user]/Medium"
//# "section_label" ist eine beliebige, eindeutige Bezeichnung für jede Sicherungsdefinition.
//# "backup_defs" beschreibt jedes zu sichernde Verzeichnis (oder Laufwerk unter Windows).
//# "backup_name" und "section_label" beschreiben die Sicherungsoption.
//# "source" ist der zu sichernde Pfad.
//# "exlude_list" ist eine Liste von zu ignorierenden Pfaden-Teilen, der vollständige 
//# Dateiname darf dies nicht enthalten.
//#
//# Alle Texte sind unter doppelte Hochkommata (Shift-2) anzugeben!
//# In der Exclude-Liste sollten alle Sonderzeichen und Leerzeichen durch "?" ersetzt werden,
//# das verhindert Probleme mit der Kodierung (ANSI, UTF-8 oder ISO 8859-1) bei der Verwendung von
//# NTFS-Partitions.
//#----------------------------------------------------------------------
''')
    cfgfile.write(json.dumps(backup_def, indent=2))
    cfgfile.close()


def is_valid_filename(fnam):
    '''Prüfen, ob Argument ein gültiger Dateiname ist (ohne :\\/...)'''
    rc = False
    pattern = r'^[a-zA-Z0-9_\-\.\+äöüßÄÖÜ]+$'
    if re.match(pattern, fnam) and 1 <= len(fnam) <= 255:
        rc = True
    else:
        rc = False

    return rc


def local_backupdef_file_exists(ba_json):
    ''' Prüfen, ob mit dieser BA-Definition wurde bereits ein Backup hier erstellt wurde,
        dann nicht nachfragen, sonst Bestätigugn einholen
    '''
    rc = False
    if not os.path.exists(ba_json):
        # ask for first time backup here
        msg = "Im Verzeichnis '{0}' wurde noch kein Backup mit dieser Konfiguration erstellt.\nBackup hier erstellen?\n".format(os.path.dirname(ba_json))
        rc = messagebox.askokcancel("Hinweis", "Erstmaliges Backup hier?", detail=msg)
    
    return rc



# ==============================================================================
class AboutBackup(tk.Toplevel):
    '''About-Info ausgeben'''

    def __init__(self, root, title, msg):        
        self.root = root
        
        self.root.title(title)
        self.root.minsize(800, 500)

        # ---- msg-Window
        fr = tk.Frame(root)
        fr.pack(side=tk.TOP, anchor=tk.N, fill=tk.BOTH, expand=1)

        self.textarea = ScrolledText(fr)
        self.textarea.pack(expand=tk.YES, fill=tk.BOTH, anchor=tk.N)
        txt = self.textarea
        txt.insert(tk.END, msg)
        txt.see("1.0")
        txt.master.update()

        # -------- Close
        fr = tk.Frame(root, padx=10, pady=10)
        fr.pack(fill=tk.X)
        tk.Button(fr, text="Schließen", command=root.destroy, anchor=tk.S).pack(side=tk.TOP)




# ==============================================================================
class ConfigBackup(tk.Toplevel):
    '''Backup Definitionen bearbeiten'''

    def __init__(self, root, section_index, tk_config_filevar):
        self.root = root
        self.section_index = section_index
        self.m_config_filevar = tk_config_filevar
        self.params = None

        self.m_dest = tk.StringVar(value=os.path.join("/media", getpass.getuser()))
        self.m_timestamp = tk.StringVar(value="True")

        self.param_labels = {
            "section_label": "Beschreibung",
            "backup_name": "Backup Name",
            "backup_destination_root": "Ziel-Basisverzeichnis",
            "use_timestamp": "Differenz-Ordner mit Zeitstempel",
            "source": "Quelle",
            "exclude_list": "Ausschließungsliste",
        }

        self.params_help = {
            "section_label": '''Bezeichnung, die im Programm als Quelle angezeigt wird, wird auch als Teil des Backup-Verzeichnisses verwendet.
            ''',
            "backup_name": '''das Verzeichnis fürs Backup unter .../backups.
            ''',
            "source": '''Verzeichnis, das gesichert werden soll, z.B. /home/USER/VERZEICHNIS.
            ''',
            "backup_destination_root": '''Basis-Zielverzeichnis fürs Backup, muss das Verzeichnis "backup" enthalten.
            ''',
            "exclude_list": '''Liste vom Backup auszuschließender Dateien/Verzeichnisse
            ''',
        }

        fr = tk.Frame(self.root)
        fr.pack(padx=30, pady=15, side=tk.TOP)
        
        # Options-Frame
        self.optionsfr = tk.Frame(self.root)
        self.optionsfr.pack(side=tk.TOP, padx=5, pady=5, expand=1, anchor=tk.W, fill=tk.BOTH)
        self.add_options()

        fr = tk.Frame (self.root)
        fr.pack(side=tk.TOP, padx=30, pady=5) #, expand=0, fill=tk.BOTH, anchor=tk.E)
        tk.Button(fr, text="Schließen", command=self.root.destroy, padx=5, pady=5, width=15).pack(side=tk.RIGHT)
        if self.m_config_filevar.get():
            txt = "Speichern"
        else:
            txt = "Speichern unter"
        tk.Button(fr, text=txt, command=self.save_cmd, padx=5, pady=5, width=15).pack(side=tk.RIGHT)

    # --------------------------------------------------------------------------


    def add_options(self):
        '''preset for new'''
        self.params = {
            "section_label": tk.StringVar(value=""),
            "backup_name": tk.StringVar(value=platform.node()),
            "source": tk.StringVar(value=os.path.expanduser("~")),
            "backup_destination_root": tk.StringVar(value=os.path.join("/media", getpass.getuser())),
            "use_timestamp": tk.StringVar(value="Nein"),
            "exclude_list": '''?RECYCLE.BIN/
MSOCache/
System?Volume?Information/
.Trash-1000/
.cache/
''', # keine tk-Variable 
        }

        if self.section_index >= 0:
            active_badef = backupdefs.get("backup_defs")[self.section_index]
            self.params["section_label"].set(active_badef.get("section_label"))
            self.params["backup_name"].set(active_badef.get("backup_name"))
            self.params["source"].set(active_badef.get("source"))
            self.params["backup_destination_root"].set(active_badef.get("backup_destination_root"))
            self.params["use_timestamp"].set(active_badef.get("use_timestamp"))
            self.params["exclude_list"] = "\n".join(active_badef.get("exclude_list"))
        

        row = 0
        for param in self.params:
            lbl = self.param_labels.get(param, param)   # Übersetzungslist, wenn nicht vorhanden, key verwenden
            tk.Label(self.optionsfr, text=lbl, width=30, anchor="e", padx=15, pady=5).grid(row=row, column=0, sticky=tk.E)
            if param != "exclude_list":
                fr = tk.Entry(self.optionsfr, textvariable=self.params[param], width=55)
                fr.grid(row=row, column=1, sticky=tk.NSEW)
            else:
                txt = self.params[param]
                maxh = len(txt.split()) + 2
                maxh = min(maxh, 15)
                self.params[param] = ScrolledText(self.optionsfr, height=maxh, width=54)
                self.params[param].grid(row=row, column=1, sticky=tk.NSEW)
                # Enter Excludes
                self.params[param].insert(tk.END, txt)
            fr.rowconfigure(row, weight=1)
            fr.columnconfigure(1, weight=1)
            self.optionsfr.columnconfigure(1, weight=1)

            row += 1

        tk.Frame(self.root, height=2, bd=1, relief=tk.SUNKEN).pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)    # -------------------------------


    def save_cmd(self):
        '''Definition speichern'''
        try:
            if backupdefs:
                # Use existing
                new_params = backupdefs
            else:
                # create Header
                new_params = {
                    "backup_defs": []
                }

            new_param = {}
            for param in self.params:
                if param == "section_label":
                    if self.params[param].get().strip() == "":
                        messagebox.showerror("Fehler", "Label falsch!", detail="Beschreibung muss angegeben werden", parent=self.root)
                        return
                    # check for unique sections
                    rc = self.check_unique_sections(self.section_index, self.params[param].get().strip().lower())
                    if rc == 0:
                        messagebox.showerror("Fehler", "Label falsch!", detail="Name bereits vergeben,\nein eindeutiger Name muss angegeben werden", parent=self.root)
                        return

                if param == "use_timestamp":
                    pass

                if param == "backup_name":
                    if not is_valid_filename(self.params[param].get()):
                        messagebox.showerror("Fehler", "Backupname fehlerhaft!", detail="'{0}' ist kein gültiger Verzeichnisname\n".format(self.params[param].get()), parent=self.root)
                        return

                if param == "source":
                    pass
                    
                if param != "exclude_list":
                    new_param[param] = self.params[param].get()
                else:
                    vals = self.params[param].get("1.0", tk.END).split("\n")
                    new_param[param] = [val.strip() for val in vals if val.strip() != ""]

            # Anhängen wenn neuer Eintrag
            if self.section_index < 0:
                new_params["backup_defs"].append(new_param.copy())
            else:
                new_params["backup_defs"][self.section_index] = new_param.copy()

            config_filename =  self.m_config_filevar.get()
            if not config_filename:
                ftypes = [("Config Files", "*.json", "JSON")]
                config_filename = filedialog.asksaveasfilename(filetypes=ftypes, initialdir=defdir, initialfile="backup_config.json", parent=self.root)
                
            # remove tk-checked-var
            if backupdefs:
                for badef in backupdefs.get("backup_defs"):
                    if "checked" in badef:
                        del badef["checked"]

            if config_filename:
                save_backup_def(config_filename, new_params)
                self.m_config_filevar.set(config_filename)
            self.root.destroy()

        except AttributeError:
            messagebox.showerror("Error", "Programmfehler", detail=traceback.format_exc(), parent=self.root)


    def check_unique_sections(self, section_ix, newval):
        '''Section-Namen müssen eindeutig sein'''
        rc = 1
        sections = []
        if self.section_index < 0:
            sections.append(newval)
        if backupdefs:
            for ix, badef in enumerate(backupdefs.get("backup_defs")):
                sections.append(badef.get("section_label").lower())
                if ix == section_ix:
                    sections[-1] = newval.lower()
            # check if not unique
            if len(sections) > len(set(sections)):
                rc = 0
        return rc




# ==============================================================================
class SetupBackup():
    '''Eintellungen und Ausführen des Backups'''

    def __init__(self, backup_type):
        #global writemsg
        # config-file und section mit der backup-def
        #writemsg("Init...\n")
        self.backup_type = backup_type
        self.cmd = None
        self.dryrun = 0
        self.active_backupdef = None
        self.backup_configdef = None
        self.sub_proc = None


    def prepare_backup(self, backupdef):
        '''Alle Einstellungen vorbereiten'''
        self.active_backupdef = backupdef.copy()
        del self.active_backupdef["checked"]

        ts = time.strftime("_%Y%m%d_%H%M%S", time.localtime())
        use_timestamp = (backupdef.get("use_timestamp").lower() in ["ja", "1", "true"])

        destination_root = backupdef.get("backup_destination_root")
        destination_backup_folder = os.path.join(destination_root, "backups")
        host = backupdef.get("backup_name")
        backup_topfolder = os.path.basename(backupdef.get("source")) 
        backupnam = backup_topfolder + "_" + host
        
        source = backupdef.get("source")
        destination = os.path.join(destination_backup_folder, host)
        excl_file = os.path.join(destination_backup_folder, backupnam + ".exclude")
        log_file = os.path.join(destination_backup_folder, backupnam + ts + ".log") 
        diff_dir = os.path.join(destination_backup_folder, backupnam + "_diff")
        self.backup_configdef = os.path.join(destination_backup_folder, backupnam + ".backupdef")
        if use_timestamp:
            diff_dir = os.path.join(destination_backup_folder, backupnam + ts)

        writemsg("\nsrc: " + source)
        writemsg("\ndes: " + destination)
        writemsg("\ndif: " + diff_dir)
        writemsg("\nexl: " + excl_file)
        writemsg("\nlog: " + log_file)
        writemsg("\n\n")

        if not os.path.exists(destination_backup_folder):
            msg = "Zielverzeichnis '{0}' nicht gefunden!\n".format(destination_backup_folder)
            writemsg(msg)
            writemsg("Verzeichnis '" + destination_backup_folder + "' überprüfen (zuerst im Dateimanager öffnen?)\n")
            messagebox.showerror("Fehler", "Verzeichnis-Fehler", detail=msg)
            return 1
        writemsg("Verzeichnis '" + destination_backup_folder + "' existiert!\n")

        if not os.path.exists(backupdef.get("source")):
            msg = "Quellverzeichnis '{0}' nicht gefunden!\n".format(backupdef.get("source"))
            writemsg(msg)
            writemsg("Verzeichnis " + backupdef.get("source") + " überprüfen (zuerst Dateimanager öffnen?)\n")
            messagebox.showerror("Fehler", "Verzeichnis-Fehler", detail=msg)
            return 1
        writemsg("Verzeichnis '" + backupdef.get("source") + "' existiert!\n")

        # check if backupdef-JSON file exists, if not ask to continue
        if not local_backupdef_file_exists(self.backup_configdef):
            return 1


        try:
            # write Exclude-List
            exf = open(excl_file, "w")
            for excl in backupdef.get("exclude_list"):
                exf.write(excl + "\n")
            exf.close()
        except IOError:
            writemsg(traceback.format_exc())
            return 1
            
        # options: v=verbose, r=recurse, i=info, u=update, skip newer files in dest, l=copy links as links, b=make backup, -t=keep mod time
        # --delete=löschen in Destination, wenn in Src nicht mehr vorhanden
        # die gelöschten Files wandern in Backup-dir
        if self.dryrun:
            dryrun_opt = "--dry-run"
        else:
            dryrun_opt = ""


        if self.backup_type == 1:            
            self.cmd = r'rsync -vritulb {dryrun} --exclude-from="{excl}" "{src}" "{dest}" | tee "{log}"'.format(dryrun=dryrun_opt, excl=excl_file, src=source, dest=destination, log=log_file)
        else:
            self.cmd = r'rsync -vritulb {dryrun} --delete --exclude-from="{excl}" --backup-dir="{bak}" "{src}" "{dest}" | tee "{log}"'.format(dryrun=dryrun_opt, excl=excl_file, bak=diff_dir, src=source, dest=destination, log=log_file)
        writemsg("\n\nrsync Aufruf:\n" + self.cmd + "\n")

        return 0    # success
    
    
    def execute_backup(self):
        '''Backup ausführen'''
        cfgfile = open(self.backup_configdef, "w")
        cfgfile.write(json.dumps(self.active_backupdef, indent=2))
        cfgfile.close()

        p = subprocess.Popen(self.cmd, bufsize=0, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.sub_proc = p
        while 1:
            out = p.stdout.readline()
            out = out.decode(encoding='UTF-8')
            if out == '' and p.poll() is not None:
                break
            if out != '':
                writemsg(out)
            else:
                break
        msg = "\n\nFertig\n====================================================================\n\n"
        writemsg(msg)


# ===========================================================================================
class ChooseBackup():
    '''Hauptmenu'''

    def open_images(self):  
        '''Open pngs'''
        icondefs = [
                    ["new", "document-new.png"], 
                    ["open", "document-open.png"],
                    ["exit", "exit.png"],
                    ["backup", "document-save.png"],
                    ["viewall", "edit-select-all.png"],
                    ["add", "list-add.png"],
                    ["edit", "accessories-text-editor.png"],
                    ["test", "applications-system.png"],
                    ["delete", "edit-delete.png"],
                    ["help", "help-browser.png"],
                    ["about", "help-about.png"],
                ]
        for icondef in icondefs:
            # Load the icon image
            if USE_PIL:
                
                iconfile = os.path.join(homedir, "bin/backup_rsync/images/", icondef[1])
                self.icons[icondef[0]] = ImageTk.PhotoImage(Image.open(iconfile))
            else:
                # go without Images
                self.icons[icondef[0]] = None


    def __init__ (self, root):
        global logwindow, defdir
        self.myparent = root
        self.sub_proc = None
        self.dryrun = 0         # Ohne schreiben
        self.m_fullbak = tk.IntVar()
        self.m_cfgfile = tk.StringVar(value="")
        self.icons = {}


        # ---- Top-Frame: Überschrift -----------------------------
        frtop = tk.Frame (root, pady=10)
        frtop.pack(expand=0, anchor=tk.N)

        # ---- Menu ------------------
        menu = tk.Menu(root)
        root.config(menu=menu)

        self.open_images()
        filemenu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Datei", menu=filemenu)
        filemenu.add_command(label=" Neue Konfigurationdatei erstellen", image=self.icons.get("new"), compound="left", command=self.create_configfile_cmd)
        filemenu.add_command(label=" Konfiguration öffnen...", image=self.icons.get("open"), compound="left", command=self.get_configfile)
        filemenu.add_command(label=" gesamte Konfiguration anzeigen", image=self.icons.get("viewall"), compound="left", command=self.show_configfile_cmd)  
        filemenu.add_separator()
        filemenu.add_command(label=" Exit", image=self.icons.get("exit"), compound="left", command=self.close_cmd)  

        editmenu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Konfiguration", menu=editmenu)
        editmenu.add_command(label=" Neuen Definition hinzufügen", image=self.icons.get("add"), compound="left", command=self.section_new_cmd)
        editmenu.add_command(label=" ausgewählten Definition bearbeiten", image=self.icons.get("edit"), compound="left", command=self.section_edit_cmd)
        editmenu.add_separator()
        editmenu.add_command(label=" ausgewählten Definition löschen", image=self.icons.get("delete"), compound="left", command=self.section_del_cmd)

        bakmenu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Backup", menu=bakmenu)
        bakmenu.add_command(label=" Testlauf mit Auswahl durchführen", image=self.icons.get("test"), compound="left", command=self.test_cmd)
        bakmenu.add_command(label=" ausgewähltes Backup erstellen", image=self.icons.get("backup"), compound="left", command=self.ok_cmd)

        helpmenu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Hilfe", menu=helpmenu)
        helpmenu.add_command(label=" Dokumentation", image=self.icons.get("help"), compound="left", command=self.backup_help)
        helpmenu.add_separator()
        helpmenu.add_command(label=" Info", image=self.icons.get("about"), compound="left", command=self.backup_about)


        # tk.Label (frtop, text="rsync-Backups", font=("Sans Bold", 12), width=35).pack()
        # tk.Frame(root, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=5)    # -------------------------------

        # ---- Backup-Config ---------------------------------------
        fr0 = tk.Frame(root, pady=20)
        fr0.pack(fill=tk.BOTH, expand=0)

        fr = tk.Frame (fr0, padx=20, pady=5)
        fr.pack(side=tk.TOP, expand=0, fill=tk.X)
        
        tk.Label(fr, text="Backup Konfiguration:", width=18).pack(side=tk.LEFT)
        tk.Entry(fr, textvariable=self.m_cfgfile, width=55, state="readonly").pack(side=tk.LEFT)
        tk.Button(fr, text="...", command=self.get_configfile).pack(side=tk.LEFT, fill=tk.X)
        tk.Button(fr, text="Anzeigen", command=self.show_configfile_cmd, width=10).pack(side=tk.LEFT, padx=5, fill=tk.X)
        tk.Button(fr, text="Neu", command=self.create_configfile_cmd, width=10).pack(side=tk.LEFT, padx=5, fill=tk.X)
       
        # --- Full-Backup Option ---------------------------------------
        fr = tk.Frame (fr0, padx=20, pady=5)
        fr.pack(side=tk.TOP, expand=0, fill=tk.X)
        tk.Checkbutton (fr, text="Komplettes Backup neu erstellen (statt inkrementellem Backup)", padx=20, pady=5, variable=self.m_fullbak).pack(side=tk.TOP, anchor=tk.W)

        tk.Frame(root, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=5) # -----------------------------

        # --- Option-Boxen und Buttons
        fr1 = tk.Frame(root, padx=20, pady=5)
        fr1.pack(side=tk.TOP, expand=1, fill=tk.X)
        
        tk.Label(fr1, text="zu sichernde Verzeichnisse/Laufwerke (Backup-Definition):", pady=5).grid(row=0, columnspan=3, sticky=tk.W)

        # -------- Welche Verzeichnisse
        self.options_frame = tk.Frame(fr1, padx=10, borderwidth=1, highlightbackground="red", highlightthickness=2)
        self.options_frame.grid(row=1, column=1, sticky=tk.NSEW)
        # Frame wird später aus der Config-Datei mit den Options gefüllt.

        # -------- OK/Cancel
        fr3 = tk.Frame (fr1, padx=10)
        fr3.grid(row=1, column=2, sticky=tk.NW)
        tk.Label(fr3, text="Einstellung").pack(side=tk.TOP)
        tk.Button(fr3, text="bearbeiten", command=self.section_edit_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)
        tk.Button(fr3, text="hinzufügen", command=self.section_new_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)
        tk.Button(fr3, text="entfernen", command=self.section_del_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)
        fr3 = tk.Frame (fr1, padx=10)
        fr3.grid(row=1, column=3, sticky=tk.NW)
        tk.Label(fr3, text="Auswahl").pack(side=tk.TOP)
        tk.Button(fr3, text="Sichern", command=self.ok_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)
        tk.Button(fr3, text="Testlauf", command=self.test_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)
        tk.Button(fr3, text="Schließen", command=self.close_cmd, padx=5, pady=5, width=15).pack(side=tk.TOP)

        # ---- Info-Line:
        fr = tk.Frame(root)
        fr.pack(side=tk.TOP, anchor=tk.N, fill=tk.BOTH, expand=0)
        tk.Label(fr, text="Achtung: Sicherungslaufwerk überprüfen!!", height=2).pack()

        # ---- Bottom Part: Log-Window
        fr = tk.Frame(root)
        fr.pack(side=tk.BOTTOM, anchor=tk.N, fill=tk.BOTH, expand=1)

        self.textarea = ScrolledText(fr)
        self.textarea.pack(expand=tk.YES, fill=tk.BOTH, anchor=tk.N)
        logwindow = self.textarea


        # Init Settings if default configfile exists
        defdir = os.path.dirname(sys.argv[0])
        cfg_filename = os.path.join(defdir, "backup_config.json")
        if os.path.exists(cfg_filename):
            self.update_form(cfg_filename)
        else:
            cfg_filename = ""

        if not backupdefs:
            msg = "Keine Standard-Backup-Konfiguration ({0}) gefunden.\n".format(cfg_filename)
            writemsg(msg)
            msg = "Wählen Sie eine Konfiguration aus oder legen sie eine neue Datei {0} an\n\n".format(cfg_filename)
            writemsg(msg)            

        if not USE_PIL:
            msg = '''Warnung: Modul PIL nicht vorhanden, es sind daher keine Icons in den Menus verfügbar.
Sie können versuchen, PIL manuell mit 'pip install pillow' zu installieren.
'''
            writemsg(msg)

    # --------------------------------------------------------------------------


    def ok_cmd(self):
        '''OK-Command'''
        self.textarea.delete(1.0, tk.END)
        self.myparent.config(cursor="watch")
        # run backup for every checked Definition
        if not backupdefs:
            messagebox.showerror("Fehler", "Keine Konfigurationsdatei geladen!", detail="Öffnen oder erzeugen Sie eine Konfiguration\n", parent=self.myparent)
        else:
            checked_cnt = 0
            for bakcfg in backupdefs.get("backup_defs"):
                checked = bakcfg.get("checked").get()
                #msg = "{0} {1}\n".format(bakcfg.get("section_label"), bakcfg.get("checked").get())
                #writemsg(msg)
                if checked:
                    checked_cnt += 1
                    self.run_backup(bakcfg)

            if checked_cnt == 0:
                messagebox.showwarning("Fehler", "Keine Quelle ausgewählt!\n", parent=self.myparent)

        self.myparent.config(cursor="")
        self.dryrun = 0


    def close_cmd(self):
        '''Fenster schließen'''
        self.myparent.destroy()


    def test_cmd(self):
        ''' Testlauf ausführen'''
        self.dryrun = 1
        self.ok_cmd()


    def create_configfile_cmd(self):
        '''Neue Konfiguration erstellen'''
        w = tk.Toplevel(self.myparent)
        old_cfg = self.m_cfgfile.get()
        ConfigBackup(w, -1, self.m_cfgfile)
        self.myparent.wait_window(w)
        if old_cfg != self.m_cfgfile.get():
            self.update_form(self.m_cfgfile.get())


    def get_checked(self):
        '''Ausgewählte Optionen suchen'''
        checked_ixs = []
        for section_ix, bakdef in enumerate(backupdefs.get("backup_defs")):
            tk_checked = bakdef.get("checked")
            if tk_checked:
                checked = tk_checked.get()
                if checked:
                    checked_ixs.append(section_ix)
        return checked_ixs


    def section_edit_cmd(self):
        '''Konfig editieren'''
        # get selected item
        if not backupdefs:
            messagebox.showerror(title="Fehler", message="Noch keine Konfiguration geladen!\n", detail="Öffnen Sie eine Backup-Definitionsdatei", parent=self.myparent)
            return

        checked_ixs = self.get_checked()
        selcnt = len(checked_ixs)
        if selcnt == 0:
            messagebox.showerror(title="Fehler", message="Keine Konfiguration ausgewählt\n", detail="Wählen Sie eine Backup-Konfiguration aus", parent=self.myparent)
            return
        if selcnt > 1:
            messagebox.showerror(title="Fehler", message="Nur eine Konfiguration auswählen\n", detail="Es kann nur eine ausgewählte Konfiguration bearbeitet werden", parent=self.myparent)
            return

        w = tk.Toplevel(self.myparent)
        ConfigBackup(w, checked_ixs[0], self.m_cfgfile)
        self.myparent.wait_window(w)
        self.update_form(self.m_cfgfile.get())
        bakcfg = backupdefs.get("backup_defs")[checked_ixs[0]]
        bakcfg["checked"].set(1)
        return
        

    def section_new_cmd(self):
        '''Config neu anlegen'''
        if not backupdefs:
            messagebox.showerror(title="Fehler", message="Noch keine Konfiguration geladen!\n", parent=self.myparent)
            return
        checked_ixs = self.get_checked()
        w = tk.Toplevel(self.myparent)
        ConfigBackup(w, -1, self.m_cfgfile)
        self.myparent.wait_window(w)
        self.update_form(self.m_cfgfile.get())
        for ix in checked_ixs:
            bakcfg = backupdefs.get("backup_defs")[ix]
            bakcfg["checked"].set(1)


    def section_del_cmd(self):
        '''Config löschen'''
        # get selected item
        if not backupdefs:
            messagebox.showerror(title="Fehler", message="Noch keine Konfiguration geladen!\n", parent=self.myparent)
            return
        checked = []
        cnt = 0
        for ix, bakdef in enumerate(backupdefs.get("backup_defs")):
            cnt += 1
            tk_checked = bakdef.get("checked")
            if tk_checked:
                if tk_checked.get():
                    checked.append(ix)

        if not checked:
            messagebox.showerror(title="Fehler", message="Keine Einstellung ausgewählt\n", parent=self.myparent)
            return
        if cnt == len(checked):
            messagebox.showerror(title="Fehler", message="Es können nicht alle Einträge gelöscht werden!\n", parent=self.myparent)
            return

        rc = messagebox.askokcancel(title="Eintrag löschen", message="Alle ausgewählte Definitionen werden gelöscht!", detail="Sind Sie sicher?\n", parent=self.myparent)
        if rc:
            for toremove in reversed(checked):
                msg = "Delete: '{0}'\n".format(backupdefs.get("backup_defs")[toremove].get("section_label"))
                writemsg(msg)
                del backupdefs.get("backup_defs")[toremove]
            
            # remove tk-checked-var
            for badef in backupdefs.get("backup_defs"):
                del badef["checked"]

            save_backup_def(self.m_cfgfile.get(), backupdefs)
            self.update_form(self.m_cfgfile.get())
            

    def show_configfile_cmd(self):
        '''Kondifuration anzeigen'''
        cfgfilename = self.m_cfgfile.get()
        if os.path.exists(cfgfilename):
            cfg = open(cfgfilename, "r")
            while 1:
                txt = cfg.readline()
                if not txt:
                    break
                writemsg(txt)
            cfg.close()



    def backup_about(self):
        '''About-Dialog anzeigen'''
        win = tk.Toplevel(self.myparent)
        AboutBackup(win, "Info", about_msg)
        self.myparent.wait_window(win)


    def backup_help(self):
        '''Hilfe-Dialog anzeigen'''
        win = tk.Toplevel(self.myparent)
        AboutBackup(win, "Beschreibung", __doc__)
        self.myparent.wait_window(win)


    def add_source_options(self):
        '''Optionen lt. Konfigfile anzeigen'''
        # Alle Option-Widgets löschen
        for wdgt in self.options_frame.winfo_children():
            wdgt.destroy()

        # neu aus Configdef aufbauen
        fr = tk.Frame(self.options_frame)
        fr.pack(side=tk.TOP, expand=1, fill=tk.BOTH)
        row=0
        for bakcfg in backupdefs.get("backup_defs"):
            lbl = bakcfg.get("backup_name").strip()
            if lbl:
                lbl += ": " + bakcfg.get("section_label")
            else:
                lbl = bakcfg.get("section_label")
            # Add Checked for selection
            bakcfg["checked"] = tk.IntVar()
            tk.Checkbutton(fr, text=lbl, padx=50, variable=bakcfg["checked"], anchor="n").grid(row=row, column=0, sticky=tk.NW)
            row += 1


    def run_backup(self, backupdef):
        '''Backup mit rsync ausführen'''
        backup_type = self.m_fullbak.get()
        #dest_root = self.m_destbase.get()

        budef = SetupBackup(backup_type)
        budef.dryrun = self.dryrun
        #budef.use_timestamp = self.m_use_timestamp.get()

        if budef.prepare_backup(backupdef) == 0:
            budef.execute_backup()


    # def get_destination_root(self):
    #     # zuerst schauen, ob Verzeichnis ein Mountpoint für externe Medien ist
    #     # dazu alle Verzeichnisse durchgehen, ob es einen Unterordner "backups" gibt, dann diesen verwenden.
    #     mountpoint_root = backupdefs.get("backup_destination_root", "")
    #     if not os.path.exists(mountpoint_root):
    #         msg = "Error: Sicherungsziel {0} existiert nicht?\n".format(mountpoint_root)
    #         writemsg(msg)
    #     else:
    #         if os.path.exists(mountpoint_root) and mountpoint_root.endswith("/backups"):
    #             self.m_destbase.set(os.path.dirname(mountpoint_root))
    #         else:
    #             # Suche nach Verzeichnis "backups" in allen unter /media/[user] eingehängten Laufwerken
    #             paths = glob.glob(os.path.join(mountpoint_root + "/*"))
    #             found = 0
    #             for path in paths:
    #                 backup_path = os.path.join(path, "backups/")
    #                 files = glob.glob(backup_path)
    #                 if files:
    #                     found += 1
    #                     self.m_destbase.set(path)
    #                 else:
    #                     msg = "Error: kein Verzeichnis 'backups' gefunden unter {0}\n".format(path)
    #                 writemsg(msg)

    #             if not self.m_destbase.get():
    #                 msg = "\nWählen Sie ein Verzeichnis, das den Ordner 'backups' enthält als Ziel aus.\n".format(mountpoint_root)
    #                 writemsg(msg)
    #             if found > 1:
    #                 msg = "Error: Mehr als ein Laufwerk unter {0} enthält ein Verzeichnis /backups\n\n".format(mountpoint_root)
    #                 writemsg(msg)
    #                 self.m_destbase.set("")


    def get_configfile(self):
        '''Config auswählen'''

        ftypes = [("Config Files", "*.json", "JSON")]
        cfgfilename = filedialog.askopenfilename(title="Konfigurationsdatei auswählen", filetypes=ftypes, initialdir=defdir, initialfile="backup_config.json", parent=self.myparent)
        if cfgfilename:
            self.update_form(cfgfilename)


    def update_form(self, cfgfilename):
        '''Formular aktualisieren mit den Optionen'''
        self.m_cfgfile.set(cfgfilename)
        load_backup_def(cfgfilename)
        self.add_source_options()


    # def get_backupdest(self):
    #     dest = filedialog.askdirectory(title="Backup-Ziel auswählen", initialdir="/", mustexist=1, parent=self.myparent)
    #     msg = "Kein Backup-Ziel ausgewählt\n"
    #     if dest:
    #         backuppath = os.path.join(dest, "backups")
    #         if os.path.exists(backuppath):
    #             self.m_destbase.set(dest)
    #             msg = "Verwende {0} als Backup-Ziel.\n".format(dest)
    #         else:
    #             msg = "Backup-Ziel {0} enthält kein Verzeichnis 'backups'!\n".format(dest)
    #             messagebox.showerror("Fehler", "ungültiges Backup-Ziel", detail=msg, parent=self.myparent)
    #     writemsg(msg)




# --------------------------------------------
def main():
    '''Main Function'''

    try:
        root = tk.Tk()
        root.wm_title("Rsync-Backups")
        #app = ChooseBackup(root)
        ChooseBackup(root)
        root.geometry('1200x700') 
        root.mainloop()

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()

# EOF:--

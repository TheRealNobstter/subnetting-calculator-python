#!/usr/bin/env python3

from ipaddress import IPv4Address, IPv4Network
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# Maximale Anzahl kompletter Subnetze, die wir direkt zeigen.
# Bei mehr Einträgen werden nur Anfang und Ende angezeigt.
MAX_VOLL_ANZEIGE = 25
ANZAHL_RAND_SUBNETZE = 10


# Eingabe prüfen

def lese_ip(text):
    """Liest und prüft die IPv4-Adresse."""
    text = text.strip()
    if text == "":
        raise ValueError("Bitte eine IPv4-Adresse eingeben.")
    try:
        return IPv4Address(text)
    except Exception as exc:
        raise ValueError("Die IPv4-Adresse hat ein ungültiges Format. Beispiel: 192.168.10.77") from exc


def lese_maske(text):
    """Liest und prüft die Maske (CIDR oder dotted decimal)."""
    text = text.strip()
    if text == "":
        raise ValueError("Bitte eine Subnetzmaske eingeben.")

    # /26 -> 26
    if text.startswith("/"):
        text = text[1:]

    # Nur Zahl: CIDR
    if text.isdigit():
        cidr = int(text)
        if 0 <= cidr <= 32:
            return cidr
        raise ValueError("CIDR muss zwischen /0 und /32 liegen.")

    # Dotted decimal
    try:
        return int(IPv4Network("0.0.0.0/" + text).prefixlen)
    except Exception as exc:
        raise ValueError("Subnetzmaske ist ungültig. Beispiel: /26 oder 255.255.255.192") from exc



def klassen_praefix(ip):
    """Ermittelt das klassische Klassenpräfix (A/B/C)."""
    erstes_oktett = int(str(ip).split(".")[0])

    if 1 <= erstes_oktett <= 126:
        return 8   # Klasse A
    if 128 <= erstes_oktett <= 191:
        return 16  # Klasse B
    if 192 <= erstes_oktett <= 223:
        return 24  # Klasse C

    raise ValueError("Diese IP liegt nicht im klassischen A/B/C-Bereich (1-223).")


def host_anzahl(prefix):
    """Berechnet Hosts pro Subnetz nach klassischer Formel (2^h - 2)."""
    host_bits = 32 - prefix

    # Sonderfälle /31 und /32
    if host_bits <= 1:
        return 0

    return (2 ** host_bits) - 2


def subnetz_anzahl(basis_prefix, ziel_prefix):
    """Liefert (klassisch_rfc950, modern_rfc1878, geliehene_bits)."""
    geliehene_bits = max(ziel_prefix - basis_prefix, 0)

    if geliehene_bits == 0:
        return 1, 1, 0

    modern = 2 ** geliehene_bits
    klassisch = max(modern - 2, 0)
    return klassisch, modern, geliehene_bits


def baue_subnetze(ip, ziel_prefix):
    """Erzeugt Hauptnetz und alle Subnetze zur Zielmaske."""
    basis_prefix = klassen_praefix(ip)

    if ziel_prefix < basis_prefix:
        raise ValueError(
            f"Die Zielmaske /{ziel_prefix} ist kleiner als das Klassenpräfix /{basis_prefix}."
        )

    hauptnetz = IPv4Network(f"{ip}/{basis_prefix}", strict=False)

    if ziel_prefix == basis_prefix:
        subnetze = [hauptnetz]
    else:
        subnetze = list(hauptnetz.subnets(new_prefix=ziel_prefix))

    return hauptnetz, subnetze, basis_prefix


def host_bereich_text(netz):
    """Gibt erste/letzte Hostadresse als Text zurück (mit Sonderfall-Hinweis)."""
    if netz.prefixlen == 32:
        return str(netz.network_address), str(netz.network_address), "Sonderfall /32: nur eine einzelne Adresse."

    if netz.prefixlen == 31:
        return str(netz.network_address), str(netz.broadcast_address), "Sonderfall /31: klassisch 0 nutzbare Hosts."

    erste = str(IPv4Address(int(netz.network_address) + 1))
    letzte = str(IPv4Address(int(netz.broadcast_address) - 1))
    return erste, letzte, ""


def subnetz_block(index, netz, markiert=False):
    """Formatiert ein Subnetz für die Textausgabe."""
    erste, letzte, hinweis = host_bereich_text(netz)
    marker = "  <= enthält eingegebene IP" if markiert else ""

    zeilen = []
    zeilen.append(f"Subnetz #{index}: {netz}{marker}")
    zeilen.append(f"  Netzadresse        : {netz.network_address}")
    zeilen.append(f"  Erste Hostadresse  : {erste}")
    zeilen.append(f"  Letzte Hostadresse : {letzte}")
    zeilen.append(f"  Broadcast-Adresse  : {netz.broadcast_address}")
    if hinweis:
        zeilen.append(f"  Hinweis            : {hinweis}")
    zeilen.append("-" * 72)
    return "\n".join(zeilen)


def ergebnis_text(ip_text, maske_text, rfc_modus="rfc1878", alle_subnetze_zeigen=False):
    """
    Hauptfunktion: prüft Eingabe, berechnet alles und gibt Text zurück.

    rfc_modus: "rfc950"
               "rfc1878"
    """
    ip = lese_ip(ip_text)
    ziel_prefix = lese_maske(maske_text)

    hauptnetz, subnetze_alle, basis_prefix = baue_subnetze(ip, ziel_prefix)
    klassisch_rfc950, modern_rfc1878, geliehene_bits = subnetz_anzahl(basis_prefix, ziel_prefix)
    hosts = host_anzahl(ziel_prefix)
    dotted = IPv4Network(f"0.0.0.0/{ziel_prefix}").netmask

    # RFC-950: erstes und letztes Subnetz weglassen (ausser bei 0 geliehenen Bits)
    if rfc_modus == "rfc950" and geliehene_bits > 0 and len(subnetze_alle) > 2:
        subnetze = subnetze_alle[1:-1]   # erstes und letztes ausschliessen
    else:
        subnetze = subnetze_alle

    # Subnetz finden, das die eingegebene IP enthält
    treffer_netz = None
    for netz in subnetze:
        if ip in netz:
            treffer_netz = netz
            break

    # RFC-Label für die Ausgabe
    if rfc_modus == "rfc950":
        rfc_label = "RFC 950  (klassisch, 2ⁿ − 2)"
        subnetze_anzeige = str(klassisch_rfc950)
        rfc_hinweis = "Erstes und letztes Subnetz sind ausgeschlossen (RFC 950)."
    else:
        rfc_label = "RFC 1878 (modern,    2ⁿ)"
        subnetze_anzeige = str(modern_rfc1878)
        rfc_hinweis = "Alle Subnetze sind nutzbar (RFC 1878)."

    zeilen = []
    zeilen.append("=" * 72)
    zeilen.append("Zusammenfassung")
    zeilen.append("=" * 72)
    zeilen.append(f"Eingegebene IP              : {ip}")
    zeilen.append(f"Klassen-Hauptnetz           : {hauptnetz}")
    zeilen.append(f"Zielmaske                   : /{ziel_prefix} ({dotted})")
    zeilen.append(f"Berechnungsmodus            : {rfc_label}")
    zeilen.append(f"Anzahl Subnetze             : {subnetze_anzeige}")
    zeilen.append(f"Hosts pro Subnetz           : {hosts}")
    if treffer_netz is not None:
        zeilen.append(f"Subnetz mit eingegebener IP : {treffer_netz}")
    zeilen.append(f"Hinweis                     : {rfc_hinweis}")

    zeilen.append("")
    zeilen.append("Kurzer Rechenweg:")
    zeilen.append(f"- Klassenpräfix    : /{basis_prefix}")
    zeilen.append(f"- Geliehene Bits   : {geliehene_bits}")
    zeilen.append(f"- Host-Bits        : {32 - ziel_prefix}")
    zeilen.append(f"- RFC 950  (2ⁿ−2)  : {klassisch_rfc950} Subnetze")
    zeilen.append(f"- RFC 1878 (2ⁿ)    : {modern_rfc1878} Subnetze")

    if ziel_prefix == 31:
        zeilen.append("- Sonderfall: /31 wird klassisch mit 0 Hosts betrachtet.")
    if ziel_prefix == 32:
        zeilen.append("- Sonderfall: /32 beschreibt genau eine Adresse.")

    zeilen.append("\n" + "=" * 72)
    zeilen.append("Subnetzdetails")
    zeilen.append("=" * 72)

    anzahl = len(subnetze)

    # Checkbox aktiv: wirklich alle Subnetze anzeigen
    if alle_subnetze_zeigen:
        for i, netz in enumerate(subnetze, start=1):
            zeilen.append(subnetz_block(i, netz, markiert=(ip in netz)))
    # Bei wenigen Subnetzen alles ausgeben
    elif anzahl <= MAX_VOLL_ANZEIGE:
        for i, netz in enumerate(subnetze, start=1):
            zeilen.append(subnetz_block(i, netz, markiert=(ip in netz)))
    else:
        # Bei vielen Subnetzen: erste 10 und letzte 10
        for i, netz in enumerate(subnetze[:ANZAHL_RAND_SUBNETZE], start=1):
            zeilen.append(subnetz_block(i, netz, markiert=(ip in netz)))

        ausgelassen = anzahl - (2 * ANZAHL_RAND_SUBNETZE)
        zeilen.append(f"... {ausgelassen} weitere Subnetze ausgelassen ...")
        zeilen.append("-" * 72)

        start_index = anzahl - ANZAHL_RAND_SUBNETZE + 1
        for i, netz in enumerate(subnetze[-ANZAHL_RAND_SUBNETZE:], start=start_index):
            zeilen.append(subnetz_block(i, netz, markiert=(ip in netz)))

    return "\n".join(zeilen)


# GUI

class SubnettingGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("IPv4-Subnetting Rechner")
        self.root.geometry("1100x750")
        self.root.minsize(900, 620)
        self.root.resizable(True, True)

        # RFC-Modus: "rfc950" oder "rfc1878"
        self.rfc_modus = tk.StringVar(value="rfc1878")
        # Anzeige-Modus: alle Subnetze ja/nein
        self.alle_subnetze_zeigen = tk.BooleanVar(value=False)

        # Animation
        self.zeilen_fuer_animation = []
        self.animation_index = 0
        self.animation_laeuft = False
        self.animation_paused = False
        self.after_id = None

        self.baue_gui()

    def baue_gui(self):
        """Erstellt alle GUI-Elemente."""
        style = ttk.Style(self.root)
        style.theme_use("clam")

        haupt = ttk.Frame(self.root, padding=16)
        haupt.pack(fill="both", expand=True)

        titel = ttk.Label(haupt, text="IPv4-Subnetting Rechner", font=("Segoe UI", 19, "bold"))
        titel.grid(row=0, column=0, columnspan=5, sticky="w")

        hinweis = ttk.Label(
            haupt,
            text="Hinweis: Dieses Programm nutzt klassisches, klassenbasiertes Subnetting (A/B/C).",
            foreground="#4b5563",
            font=("Segoe UI", 10),
        )
        hinweis.grid(row=1, column=0, columnspan=5, sticky="w", pady=(2, 10))

        # IP + Maske
        ttk.Label(haupt, text="IPv4-Adresse:").grid(row=2, column=0, sticky="w")
        self.ip_entry = ttk.Entry(haupt, width=28, font=("Segoe UI", 12))
        self.ip_entry.grid(row=2, column=1, sticky="w", padx=(6, 18))

        ttk.Label(haupt, text="Subnetzmaske:").grid(row=2, column=2, sticky="w")
        self.maske_entry = ttk.Entry(haupt, width=28, font=("Segoe UI", 12))
        self.maske_entry.grid(row=2, column=3, sticky="w", padx=(6, 0))

        input_info = ttk.Label(
            haupt,
            text="Beispiele: 192.168.10.77 | /26 oder 255.255.255.192",
            foreground="#6b7280",
        )
        input_info.grid(row=3, column=0, columnspan=5, sticky="w", pady=(4, 8))

        # RFC-Auswahl
        rfc_frame = ttk.LabelFrame(haupt, text="Berechnungsmodus", padding=(10, 6))
        rfc_frame.grid(row=4, column=0, columnspan=5, sticky="w", pady=(0, 10))

        ttk.Radiobutton(
            rfc_frame,
            text="RFC 1878",
            variable=self.rfc_modus,
            value="rfc1878",
        ).pack(side="left", padx=(0, 20))

        ttk.Radiobutton(
            rfc_frame,
            text="RFC 950",
            variable=self.rfc_modus,
            value="rfc950",
        ).pack(side="left")

        ttk.Checkbutton(
            rfc_frame,
            text="Alle Subnetze anzeigen",
            variable=self.alle_subnetze_zeigen,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=(20, 0))

        # Buttons
        button_frame = ttk.Frame(haupt)
        button_frame.grid(row=5, column=0, columnspan=5, sticky="w", pady=(0, 10))

        ttk.Button(button_frame, text="Berechnen", command=self.berechnen).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Pause", command=self.animation_pause).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Play", command=self.animation_play).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Leeren", command=self.leeren).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Beispiel laden", command=self.beispiel_laden).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Ergebnis kopieren", command=self.ergebnis_kopieren).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Vollbild", command=self.vollbild_toggle).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Beenden", command=self.root.destroy).pack(side="left")

        # Ausgabe
        self.ausgabe = ScrolledText(haupt, wrap="word", font=("Consolas", 11), padx=10, pady=10)
        self.ausgabe.grid(row=6, column=0, columnspan=5, sticky="nsew")

        footer = ttk.Label(haupt, text="Nobstter", foreground="#9ca3af")
        footer.grid(row=7, column=4, sticky="se", pady=(8, 0))

        haupt.columnconfigure(1, weight=1)
        haupt.columnconfigure(3, weight=1)
        haupt.rowconfigure(6, weight=1)

        self.root.bind("<Return>", lambda _e: self.berechnen())
        self.root.bind("<Escape>", lambda _e: self.root.attributes("-fullscreen", False))

        # Startwerte
        self.beispiel_laden()

    def stoppe_animation(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.animation_laeuft = False
        self.animation_paused = False

    def starte_animation(self, text):
        """Zeigt den Ergebnistext zeilenweise mit after() an."""
        self.stoppe_animation()
        self.ausgabe.delete("1.0", tk.END)

        self.zeilen_fuer_animation = text.splitlines()
        self.animation_index = 0
        self.animation_laeuft = True
        self.animation_paused = False

        self.naechste_zeile_anzeigen()

    def naechste_zeile_anzeigen(self):
        """Fügt die nächste Zeile ein. So friert die GUI nicht ein."""
        if not self.animation_laeuft:
            return

        if self.animation_paused:
            return

        if self.animation_index >= len(self.zeilen_fuer_animation):
            self.animation_laeuft = False
            self.after_id = None
            return

        zeile = self.zeilen_fuer_animation[self.animation_index]
        self.ausgabe.insert(tk.END, zeile + "\n")
        self.ausgabe.see(tk.END)
        self.animation_index += 1

        # 18 ms/Zeile: flüssig, aber lesbar
        self.after_id = self.root.after(18, self.naechste_zeile_anzeigen)

    def animation_pause(self):
        """Pausiert die laufende Ausgabe."""
        if not self.animation_laeuft:
            return
        self.animation_paused = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def animation_play(self):
        """Setzt die pausierte Ausgabe fort."""
        if not self.animation_laeuft:
            return
        if not self.animation_paused:
            return
        self.animation_paused = False
        self.naechste_zeile_anzeigen()

    def berechnen(self):
        ip_text = self.ip_entry.get()
        maske_text = self.maske_entry.get()
        rfc_modus = self.rfc_modus.get()   # "rfc950" oder "rfc1878"
        alle_subnetze_zeigen = self.alle_subnetze_zeigen.get()

        try:
            text = ergebnis_text(ip_text, maske_text, rfc_modus, alle_subnetze_zeigen)
        except ValueError as exc:
            messagebox.showerror("Eingabefehler", str(exc))
            return

        self.starte_animation(text)

    def leeren(self):
        self.stoppe_animation()
        self.ip_entry.delete(0, tk.END)
        self.maske_entry.delete(0, tk.END)
        self.ausgabe.delete("1.0", tk.END)
        self.ip_entry.focus_set()

    def beispiel_laden(self):
        """Lädt einen einfachen Beispielwert."""
        self.ip_entry.delete(0, tk.END)
        self.maske_entry.delete(0, tk.END)
        self.ip_entry.insert(0, "192.168.10.77")
        self.maske_entry.insert(0, "/26")
        self.ip_entry.focus_set()

    def ergebnis_kopieren(self):
        """Kopiert den aktuellen Ergebnistext in die Zwischenablage."""
        text = self.ausgabe.get("1.0", tk.END).strip()
        if text == "":
            messagebox.showinfo("Hinweis", "Es gibt noch kein Ergebnis zum Kopieren.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Kopiert", "Ergebnis wurde in die Zwischenablage kopiert.")

    def vollbild_toggle(self):
        """Schaltet Vollbild ein/aus."""
        aktuell = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not aktuell)


def main():
    """Programmstart."""
    root = tk.Tk()
    SubnettingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
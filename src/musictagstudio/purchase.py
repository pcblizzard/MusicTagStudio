"""Kauf-Optionen für Premium mit fester Laufzeit (PayPal-Festpreis-Buttons).

Jede Laufzeit ist ein eigener **PayPal-„Hosted Button"** mit *festem,
unveränderbarem* Betrag (nicht der Spenden-Button, der beliebige Beträge
zulässt). Die zugehörige Keygen-Policy vergibt die passende Laufzeit
(``duration``); der erzeugte Lizenzschlüssel trägt dann automatisch das
Ablaufdatum, das die App bereits auswertet (:mod:`licensing_keygen`).

So richtest du es ein:
1. Im PayPal-Dashboard je Laufzeit einen Button mit festem Preis anlegen.
2. Die jeweilige ``hosted_button_id`` unten eintragen (und optional den
   Anzeigepreis).
3. In Keygen je Laufzeit eine Policy (30 / 180 / 365 Tage bzw. unbefristet)
   anlegen und nach Zahlung einen Schlüssel darunter erzeugen.

Nur Optionen mit gesetzter ``hosted_button_id`` werden in der App angezeigt.
"""

from __future__ import annotations

from dataclasses import dataclass

_PAYPAL_BUTTON_BASE = (
    "https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id="
)


@dataclass(frozen=True)
class PurchaseOption:
    label_key: str
    months: int | None  # None = Lebenslang (unbefristet)
    hosted_button_id: str = ""
    price: str = ""  # optionaler Anzeigepreis, z. B. "4,99 €"

    @property
    def url(self) -> str:
        return _PAYPAL_BUTTON_BASE + self.hosted_button_id if self.hosted_button_id else ""

    @property
    def configured(self) -> bool:
        return bool(self.hosted_button_id.strip())


# ----- HIER die PayPal-Button-IDs (und optional Preise) eintragen ------------
PURCHASE_OPTIONS: tuple[PurchaseOption, ...] = (
    PurchaseOption("premium_buy_1m", months=1, hosted_button_id="", price=""),
    PurchaseOption("premium_buy_6m", months=6, hosted_button_id="", price=""),
    PurchaseOption("premium_buy_12m", months=12, hosted_button_id="", price=""),
    PurchaseOption("premium_buy_lifetime", months=None, hosted_button_id="", price=""),
)


def configured_options() -> tuple[PurchaseOption, ...]:
    """Nur die Laufzeiten, für die ein PayPal-Button hinterlegt ist."""
    return tuple(option for option in PURCHASE_OPTIONS if option.configured)

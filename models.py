from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from datetime import datetime, date, timedelta, timezone

db = SQLAlchemy()


def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

PIPELINE_STAGES = [
    ('new', 'Neu'),
    ('contacted', 'Kontaktiert'),
    ('qualified', 'Qualifiziert'),
    ('proposal', 'Angebot'),
    ('negotiation', 'Verhandlung'),
    ('won', 'Gewonnen'),
    ('on_hold', 'Auf Hold'),
    ('lost', 'Verloren'),
    ('closed_no_response', 'Keine Antwort'),
]

DEAD_PIPELINE_STAGES = ('lost', 'closed_no_response')

DEAL_PROBABILITY_DEFAULTS = {
    'new': 5, 'contacted': 10, 'qualified': 25,
    'proposal': 50, 'negotiation': 75, 'won': 100, 'lost': 0,
    'on_hold': 0
}

LOST_REASONS = [
    ('budget', 'Budget / Zu teuer'),
    ('timing', 'Timing passt nicht'),
    ('competitor', 'Wettbewerb gewaehlt'),
    ('no_need', 'Kein Bedarf'),
    ('no_response', 'Keine Antwort'),
    ('other', 'Sonstiges'),
]

ANREDE_OPTIONS = [
    ('', '-'),
    ('Herr', 'Herr'),
    ('Frau', 'Frau'),
    ('Firma', 'Firma'),
]

ANREDE_EN_OPTIONS = [
    ('', '-'),
    ('Mr.', 'Mr.'),
    ('Ms.', 'Ms.'),
    ('Mrs.', 'Mrs.'),
    ('Dr.', 'Dr.'),
]

KONTAKT_WIE_OPTIONS = [
    ('', '-'),
    ('E-Mail', 'E-Mail'),
    ('Telefon', 'Telefon'),
    ('LinkedIn', 'LinkedIn'),
    ('Persönlich', 'Persönlich'),
    ('Messe', 'Messe'),
    ('Empfehlung', 'Empfehlung'),
]

SPRACHE_OPTIONS = [
    ('', '-'),
    ('Deutsch', 'Deutsch'),
    ('Englisch', 'Englisch'),
    ('Französisch', 'Französisch'),
    ('Italienisch', 'Italienisch'),
    ('Spanisch', 'Spanisch'),
]

QUELLEN_OPTIONS = [
    ('', '-'),
    ('linkedin', 'LinkedIn'),
    ('email', 'E-Mail Outreach'),
    ('messe', 'Messe'),
    ('empfehlung', 'Empfehlung'),
    ('website', 'Website'),
    ('cold_call', 'Cold Call'),
    ('partneragentur', 'partneragentur (Kooperation)'),
    ('other', 'Sonstiges'),
]

DEFAULT_HOURLY_RATE = 100
PARTNERAGENTUR_HOURLY_RATE = 90

BRANCHEN_OPTIONS = [
    ('', '-'),
    ('saas', 'SaaS / Software'),
    ('beratung', 'Beratung'),
    ('handel', 'Handel'),
    ('industrie', 'Industrie'),
    ('bildung', 'Bildung'),
    ('gesundheit', 'Gesundheit'),
    ('finanzen', 'Finanzen'),
    ('other', 'Sonstiges'),
]

PRIORITAET_OPTIONS = [('A', 'A - Hoch'), ('B', 'B - Mittel'), ('C', 'C - Niedrig')]

TIER_OPTIONS = [
    ('', '-'),
    ('starter', 'Starter'),
    ('standard', 'Standard'),
    ('premium', 'Premium'),
]

PIPELINE_PHASE_OPTIONS = [
    ('', '-'),
    ('0.7', '0.7 — Erstgespräch'),
    ('1.1', '1.1 — Kundenanalyse'),
    ('1.2', '1.2 — Brand Book'),
    ('1.3', '1.3 — Keyword-Recherche'),
    ('1.4', '1.4 — Angebot'),
    ('1.5', '1.5 — Fördercheck'),
    ('2.1', '2.1 — Informationsarchitektur'),
    ('2.2', '2.2 — Technisches Fundament'),
    ('2.3', '2.3 — Website-Erstellung'),
    ('2.4', '2.4 — Tracking-Setup'),
    ('2.5', '2.5 — Conversion-Tracking'),
    ('3.1', '3.1 — SEO Content'),
    ('3.2', '3.2 — GEO Content'),
    ('3.3', '3.3 — CRO'),
    ('3.4', '3.4 — Social Media Strategie'),
    ('4.1', '4.1 — Google Ads Design'),
    ('4.2', '4.2 — Google Grants Setup'),
    ('4.3', '4.3 — Meta Ads Design'),
    ('4.4', '4.4 — Bulk Upload'),
    ('5.0', '5.0 — Laufende Betreuung'),
    ('6.3', '6.3 — Handover'),
]

ABRECHNUNGSMODELL_OPTIONS = [
    ('retainer', 'Retainer (Monatspauschale)'),
    ('retainer_trueup', 'Retainer mit True-Up'),
    ('stundenbasis', 'Stundenabrechnung'),
    ('projekt_fix', 'Fixpreis-Projekt'),
    ('agentur_partner', 'Über partneragentur abgerechnet'),
    ('aufwand_extern', 'Aufwand extern verguetet'),
    ('pro_bono', 'Pro bono (unentgeltlich)'),
    ('lead_quote', 'Angebot offen'),
    ('paused', 'Pausiert'),
    ('lost', 'Kein Mandat (verloren)'),
    ('intern', 'Eigenarbeit (DW selbst)'),
]

FOLLOWUP_DEFAULTS = {
    'new': 3,
    'contacted': 7,
    'qualified': 14,
    'proposal': 7,
    'negotiation': 5,
}

GOAL_PERIOD_TYPES = [('monthly', 'Monatlich'), ('quarterly', 'Quartalsweise')]

TAETIGKEIT_KONTAKT_OPTIONS = [
    ('anbahnung', 'Anbahnung'),
    ('vorgespraeche', 'Kostenlose Vorgespräche'),
    ('angebotserstellung', 'Angebotserstellung'),
    ('onboarding', 'Onboarding'),
    ('meetings', 'Meetings'),
    ('beratung', 'Beratung / Konzept / Strategie'),
    ('keywordrecherche', 'Keywordrecherche'),
    ('inhaltserstellung', 'Inhaltserstellung'),
    ('entwicklung', 'Entwicklung'),
    ('menuefuehrung', 'Menüführung'),
    ('setup_tracking', 'Setup Tracking'),
    ('setup_seo_geo', 'Setup SEO/GEO'),
    ('setup_reporting', 'Setup Reporting'),
    ('setup_zielgruppen', 'Zielgruppen-Definition'),
    ('setup_kanalstrategie', 'Kanalstrategie'),
    ('setup_google_ads', 'Setup Google Ads'),
    ('setup_meta_ads', 'Setup Meta Ads'),
    ('setup_microsoft_ads', 'Setup Microsoft Ads'),
    ('pflege_google_ads', 'Laufende Pflege Google Ads'),
    ('pflege_meta_ads', 'Laufende Pflege Meta Ads'),
    ('kontaktpflege', 'Kontaktpflege'),
    ('administration', 'Administration'),
]

TAETIGKEIT_ALLGEMEIN_OPTIONS = [
    ('stellwerk', 'Stellwerk (Eigenentwicklung)'),
    ('tooling', 'Tooling / Automatisierung'),
    ('fundament_kundenarbeit', 'Fundament für Kundenarbeit'),
    ('marketing_eigenes', 'Eigenmarketing'),
    ('akquise', 'Akquise / Vertrieb'),
    ('netzwerken', 'Netzwerken'),
    ('weiterbildung', 'Weiterbildung'),
    ('buchhaltung', 'Buchhaltung / Finanzen'),
    ('sonstiges', 'Sonstiges'),
]

DOC_TYPES = [('quote', 'Angebot'), ('invoice', 'Rechnung')]

QUOTE_STATUSES = [
    ('draft', 'Entwurf'),
    ('sent', 'Gesendet'),
    ('accepted', 'Angenommen'),
    ('converted', 'In Rechnung'),
    ('rejected', 'Abgelehnt'),
    ('expired', 'Abgelaufen'),
    ('cancelled', 'Storniert'),
]
QUOTE_WON_STATUSES = ('accepted', 'converted')
INVOICE_STATUSES = [
    ('draft', 'Entwurf'),
    ('sent', 'Gesendet'),
    ('paid', 'Bezahlt'),
    ('overdue', 'Ueberfaellig'),
    ('cancelled', 'Storniert'),
]

CONTACT_TYPES = [
    ('customer', 'Kunde'),
    ('supplier', 'Lieferant'),
    ('both', 'Kunde & Lieferant'),
]
INCOMING_INVOICE_STATUSES = [
    ('open', 'Offen'),
    ('paid', 'Bezahlt'),
    ('cancelled', 'Storniert'),
]
PAYMENT_METHODS = [
    ('sepa', 'SEPA / Banküberweisung'),
    ('kreditkarte', 'Kreditkarte'),
    ('lastschrift', 'Lastschrift'),
    ('paypal', 'PayPal'),
    ('bar', 'Bar'),
    ('privateinlage', 'Privat bezahlt (Privateinlage)'),
    ('sonstiges', 'Sonstiges'),
]
BELEG_STATUSES = [
    ('fehlt', 'Beleg fehlt'),
    ('vorhanden', 'PDF vorhanden'),
    ('geprueft', 'Geprüft / kontiert'),
]

UNIT_OPTIONS = [
    ('Einmalig', 'Einmalig'),
    ('Monatlich', 'Monatlich'),
    ('Pro Kanal', 'Pro Kanal'),
    ('Stunde', 'Stunde'),
    ('Pauschal', 'Pauschal'),
]

BILLING_TYPES = [('onetime', 'Einmalig'), ('recurring', 'Laufend')]

DEFAULT_CONDITIONS_PRESETS = [
    ('14_tage', 'Standard 14 Tage', 'Zahlbar innerhalb von 14 Tagen ab Rechnungsdatum ohne Abzug. Es gelten unsere AGB.'),
    ('30_tage', '30 Tage', 'Zahlbar innerhalb von 30 Tagen ab Rechnungsdatum ohne Abzug. Es gelten unsere AGB.'),
    ('sofort', 'Sofort fällig', 'Der Rechnungsbetrag ist sofort nach Erhalt ohne Abzug fällig. Es gelten unsere AGB.'),
    ('angebot', 'Angebot Standard', 'Alle Preise verstehen sich in Euro, exkl. USt. Dieses Angebot ist 30 Tage gültig. Nicht enthaltene Leistungen werden nach Aufwand verrechnet.'),
]

DUNNING_LEVELS = {
    1: {'days': 14, 'title': 'Zahlungserinnerung', 'tone': 'freundlich'},
    2: {'days': 28, 'title': '1. Mahnung', 'tone': 'bestimmt'},
    3: {'days': 35, 'title': '2. Mahnung', 'tone': 'deutlich'},
}

BOARD_STAGES = [
    ('backlog', 'Backlog', 'slate'),
    ('todo', 'To Do', 'blue'),
    ('in_arbeit', 'In Arbeit', 'violet'),
    ('review', 'Review', 'cyan'),
    ('erledigt', 'Erledigt', 'emerald'),
]

TASK_STALE_THRESHOLD_DAYS = 30

BOARD_SCHEDULED_LEAD_DAYS = 14

BOARD_PRIORITY_OPTIONS = [
    ('hoch', 'Hoch'),
    ('mittel', 'Mittel'),
    ('niedrig', 'Niedrig'),
]

CONTENT_CALENDAR_STAGES = [
    ('rohentwurf',    'Rohentwurf',        'red'),
    ('text_fertig',   'Text/Copy fertig',  'orange'),
    ('visual_fertig', 'Bild/Video fertig', 'amber'),
    ('scheduled',     'Scheduled',         'lime'),
    ('posted',        'Posted',            'green'),
]

CONTENT_PLATFORMS = [
    ('blog', 'Blog'),
    ('instagram', 'Instagram'), ('instagram_story', 'Instagram Story'),
    ('facebook', 'Facebook'),
    ('linkedin', 'LinkedIn (Profil)'), ('linkedin_page', 'LinkedIn (Seite)'),
    ('youtube', 'YouTube'), ('pinterest', 'Pinterest'),
    ('threads', 'Threads'), ('tiktok', 'TikTok'), ('x', 'X'),
    ('google_business', 'Google Unternehmensprofil'),
]

CONTENT_TAKT_EINHEITEN = [
    ('woche', 'Woche', 'Wochen'),
    ('monat', 'Monat', 'Monate'),
]

BOARD_EFFORT_OPTIONS = [
    ('xs', 'XS'),
    ('s', 'S'),
    ('m', 'M'),
    ('l', 'L'),
    ('xl', 'XL'),
]

BOARD_IMPACT_OPTIONS = [
    ('hoch', 'Hoch'),
    ('mittel', 'Mittel'),
    ('niedrig', 'Niedrig'),
]

CREATED_BY_OPTIONS = ['Max', 'Claude', 'System']

SERVICE_CATEGORIES = [
    ('webdesign', 'Webdesign'),
    ('seo_geo', 'SEO & GEO'),
    ('digitales_1x1', 'Digitales 1x1'),
    ('performance_marketing', 'Performance Marketing'),
    ('reporting', 'Reporting'),
    ('fremdkosten', 'Fremdkosten direkt an Dritte'),
]

RECURRENCE_PRESETS = [
    (1, 'Täglich'),
    (7, 'Wöchentlich'),
    (14, 'Zweiwöchentlich'),
    (21, 'Alle 3 Wochen'),
    (30, 'Monatlich'),
    (90, 'Quartalsweise'),
]

PRIORITY_SCORES = {'hoch': 3, 'mittel': 2, 'niedrig': 1}
IMPACT_SCORES = {'hoch': 3, 'mittel': 2, 'niedrig': 1}
EFFORT_SCORES = {'xs': 1, 's': 2, 'm': 3, 'l': 5, 'xl': 8}


class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)

    organisation = db.Column(db.String(300))
    organisationsform = db.Column(db.String(100))
    website = db.Column(db.String(300))
    mail_organisation = db.Column(db.String(200))
    telefon_organisation = db.Column(db.String(50))
    in_a_nutshell = db.Column(db.Text)
    land = db.Column(db.String(100))
    bundesland = db.Column(db.String(100))
    plz = db.Column(db.String(20))
    stadt = db.Column(db.String(100))
    strasse = db.Column(db.String(300))

    sprache_1 = db.Column(db.String(50))
    sprache_2 = db.Column(db.String(50))

    vorname = db.Column(db.String(100))
    nachname = db.Column(db.String(100))
    mail_person = db.Column(db.String(200))
    mail_rechnung = db.Column(db.String(200))
    telefon_person = db.Column(db.String(50))
    position = db.Column(db.String(200))
    anrede = db.Column(db.String(50))
    anrede_en = db.Column(db.String(50))
    titel_vor = db.Column(db.String(100))
    titel_nach = db.Column(db.String(100))
    linkedin = db.Column(db.String(300))

    gruendungsdatum = db.Column(db.Date, nullable=True)

    steuernummer = db.Column(db.String(100))
    uid = db.Column(db.String(100))
    firmenbuchnummer = db.Column(db.String(100))

    stammdaten_verifiziert = db.Column(db.Boolean, default=False)

    rechnung_name = db.Column(db.String(300))
    rechnung_uid = db.Column(db.String(100))
    rechnung_strasse = db.Column(db.String(300))
    rechnung_plz = db.Column(db.String(20))
    rechnung_stadt = db.Column(db.String(100))
    rechnung_land = db.Column(db.String(100))

    contact_type = db.Column(db.String(10), nullable=False, default='customer')

    gemeinnuetzig = db.Column(db.Boolean, default=False)

    kontaktiert = db.Column(db.Date)
    wie = db.Column(db.String(100))
    kommentare = db.Column(db.Text)

    erinnerung = db.Column(db.Date)
    erinnerungstext = db.Column(db.String(500))

    status = db.Column(db.String(50), default='new')
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    deal_value = db.Column(db.Float, nullable=True)
    deal_probability = db.Column(db.Integer, nullable=True)

    lost_reason = db.Column(db.String(100), nullable=True)

    quelle = db.Column(db.String(100), nullable=True)
    branche = db.Column(db.String(100), nullable=True)
    prioritaet = db.Column(db.String(10), default='B')

    customer_number = db.Column(db.String(20), unique=True, nullable=True)

    hourly_rate = db.Column(db.Float, nullable=True, default=DEFAULT_HOURLY_RATE)

    tier = db.Column(db.String(20), nullable=True)
    pipeline_phase = db.Column(db.String(10), nullable=True)

    abrechnungsmodell = db.Column(db.String(50), nullable=True)

    abrechnung_terminiert_bis = db.Column(db.Date, nullable=True)

    has_social_mandate = db.Column(db.Boolean, nullable=False, default=False)

    mandat_aktiv = db.Column(db.Boolean, nullable=False, default=False)

    lead_score = db.Column(db.Integer, default=0)

    archived = db.Column(db.Boolean, nullable=False, default=False)

    interactions = db.relationship('Interaction', backref='contact', lazy=True,
                                   cascade='all, delete-orphan',
                                   order_by='Interaction.datum.desc(), Interaction.created_at.desc()')
    status_changes = db.relationship('StatusChange', backref='contact', lazy=True,
                                      cascade='all, delete-orphan',
                                      order_by='StatusChange.changed_at.desc()')
    time_entries = db.relationship('TimeEntry', backref='contact', lazy=True,
                                    cascade='all, delete-orphan',
                                    order_by='TimeEntry.datum.desc(), TimeEntry.created_at.desc()')
    documents = db.relationship('Document', backref='contact', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='Document.date.desc()')
    expected_payments = db.relationship('ExpectedPayment', backref='contact', lazy=True,
                                         cascade='all, delete-orphan',
                                         order_by='ExpectedPayment.expected_date')
    accounts = db.relationship('CustomerAccount', backref='contact', lazy=True,
                                cascade='all, delete-orphan',
                                order_by='CustomerAccount.id')

    @property
    def display_name(self):
        if self.organisation:
            return self.organisation
        parts = [self.vorname, self.nachname]
        name = ' '.join(p for p in parts if p)
        return name or 'Unbenannter Kontakt'

    @property
    def full_name(self):
        parts = [self.titel_vor, self.vorname, self.nachname]
        name = ' '.join(p for p in parts if p)
        if self.titel_nach:
            name = f"{name}, {self.titel_nach}" if name else self.titel_nach
        return name

    @property
    def primary_email(self):
        return self.mail_person or self.mail_organisation

    @property
    def billing_email(self):
        return self.mail_rechnung or self.primary_email

    @property
    def billing_name(self):
        return self.rechnung_name or self.organisation

    @property
    def billing_uid(self):
        return self.rechnung_uid or self.uid

    @property
    def billing_strasse(self):
        return self.rechnung_strasse or self.strasse

    @property
    def billing_plz(self):
        return self.rechnung_plz or self.plz

    @property
    def billing_stadt(self):
        return self.rechnung_stadt or self.stadt

    @property
    def billing_land(self):
        return self.rechnung_land or self.land

    @property
    def primary_phone(self):
        return self.telefon_person or self.telefon_organisation

    @property
    def weighted_value(self):
        if not self.deal_value:
            return 0
        prob = self.deal_probability if self.deal_probability is not None else DEAL_PROBABILITY_DEFAULTS.get(self.status, 0)
        return self.deal_value * prob / 100

    @property
    def time_value(self):
        if not self.hourly_rate:
            return 0
        total_min = sum(e.dauer_minuten for e in self.time_entries if e.timer_start is None)
        return round(total_min / 60 * self.hourly_rate, 2)

    @property
    def expected_payments_total(self):
        return sum(p.amount for p in self.expected_payments if p.status == 'pending')

    @property
    def received_payments_total(self):
        return sum(p.amount for p in self.expected_payments if p.status == 'received')

    @property
    def profitability(self):
        return round(self.received_payments_total - self.time_value, 2)


class Interaction(db.Model):
    __tablename__ = 'interactions'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    typ = db.Column(db.String(100), nullable=False)
    notiz = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow_naive)


task_tags = db.Table('task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag', db.String(100), primary_key=True)
)


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='backlog')
    priority = db.Column(db.String(10), nullable=False, default='mittel')
    effort = db.Column(db.String(5))
    impact = db.Column(db.String(10))
    score = db.Column(db.Float)
    category = db.Column(db.String(100))
    due_date = db.Column(db.Date)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    created_by = db.Column(db.String(50), nullable=False, default='Max')
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    completed_at = db.Column(db.DateTime)
    position = db.Column(db.Integer, nullable=False, default=0)
    recurrence_days = db.Column(db.Integer)

    contact = db.relationship('Contact', backref=db.backref('tasks', lazy=True))
    comments = db.relationship('TaskComment', backref='task', lazy=True, cascade='all, delete-orphan',
                               order_by='TaskComment.created_at')

    @validates('status')
    def _validate_status(self, key, value):
        allowed = {s[0] for s in BOARD_STAGES}
        if value not in allowed:
            raise ValueError(
                f"Ungueltiger Task-Status '{value}'. Erlaubt (BOARD_STAGES): "
                f"{', '.join(s[0] for s in BOARD_STAGES)}"
            )
        return value

    def calculate_score(self):
        if self.impact and self.effort:
            self.score = (IMPACT_SCORES[self.impact] * PRIORITY_SCORES[self.priority]) / EFFORT_SCORES[self.effort]
        else:
            self.score = None

    @property
    def display_score(self):
        return f'{self.score:.1f}' if self.score is not None else None

    @property
    def days_since_update(self):
        if not self.updated_at:
            return None
        return (date.today() - self.updated_at.date()).days

    @property
    def is_stale(self):
        if self.status == 'erledigt':
            return False
        days = self.days_since_update
        return days is not None and days > TASK_STALE_THRESHOLD_DAYS


class TaskComment(db.Model):
    __tablename__ = 'task_comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)


class ContentCalendarEntry(db.Model):
    __tablename__ = 'content_calendar'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    platform = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='idee')
    title = db.Column(db.String(200), nullable=False)
    content_text = db.Column(db.Text, nullable=True)
    asset_link = db.Column(db.String(500), nullable=True)
    scheduled_for = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    posted_at = db.Column(db.DateTime, nullable=True)
    outbox_job = db.Column(db.String(80), nullable=True)

    contact = db.relationship('Contact', backref=db.backref('content_entries', lazy=True))

    @validates('status')
    def _validate_status(self, key, value):
        allowed = {s[0] for s in CONTENT_CALENDAR_STAGES}
        if value not in allowed:
            raise ValueError(
                f"Ungueltiger Content-Kalender-Status '{value}'. Erlaubt (CONTENT_CALENDAR_STAGES): "
                f"{', '.join(s[0] for s in CONTENT_CALENDAR_STAGES)}"
            )
        return value

    @validates('platform')
    def _validate_platform(self, key, value):
        allowed = {p[0] for p in CONTENT_PLATFORMS}
        if value not in allowed:
            raise ValueError(
                f"Ungueltige Plattform '{value}'. Erlaubt (CONTENT_PLATFORMS): "
                f"{', '.join(p[0] for p in CONTENT_PLATFORMS)}"
            )
        return value

    @property
    def is_overdue(self):
        if not self.scheduled_for:
            return False
        if self.status in ('scheduled', 'posted'):
            return False
        return self.scheduled_for.date() <= datetime.now().date()


class ContentTakt(db.Model):
    __tablename__ = 'content_takte'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    anzahl = db.Column(db.Integer, nullable=False, default=1)
    intervall = db.Column(db.Integer, nullable=False, default=1)
    einheit = db.Column(db.String(10), nullable=False, default='woche')
    gueltig_ab = db.Column(db.Date, nullable=True)
    gueltig_bis = db.Column(db.Date, nullable=True)
    notiz = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    contact = db.relationship('Contact', backref=db.backref('content_takte', lazy=True))

    @validates('platform')
    def _validate_platform(self, key, value):
        if value not in {p[0] for p in CONTENT_PLATFORMS}:
            raise ValueError(f"Ungueltige Plattform '{value}' (CONTENT_PLATFORMS)")
        return value

    @validates('einheit')
    def _validate_einheit(self, key, value):
        if value not in {e[0] for e in CONTENT_TAKT_EINHEITEN}:
            raise ValueError(f"Ungueltige Einheit '{value}' (CONTENT_TAKT_EINHEITEN)")
        return value

    @validates('anzahl', 'intervall')
    def _validate_positiv(self, key, value):
        if value is None or int(value) < 1:
            raise ValueError(f"{key} muss mindestens 1 sein")
        return int(value)


class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    betreff = db.Column(db.String(500), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)


class StatusChange(db.Model):
    __tablename__ = 'status_changes'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    from_status = db.Column(db.String(50), nullable=True)
    to_status = db.Column(db.String(50), nullable=False)
    deal_value_at_change = db.Column(db.Float, nullable=True)
    changed_at = db.Column(db.DateTime, default=utcnow_naive)


class SalesGoal(db.Model):
    __tablename__ = 'sales_goals'

    id = db.Column(db.Integer, primary_key=True)
    period_type = db.Column(db.String(20), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    @property
    def period_end(self):
        if self.period_type == 'quarterly':
            month = self.period_start.month + 3
            year = self.period_start.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            return self.period_start.replace(year=year, month=month, day=1) - timedelta(days=1)
        else:
            month = self.period_start.month + 1
            year = self.period_start.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            return self.period_start.replace(year=year, month=month, day=1) - timedelta(days=1)

    @property
    def label(self):
        if self.period_type == 'quarterly':
            q = (self.period_start.month - 1) // 3 + 1
            return f'Q{q} {self.period_start.year}'
        return self.period_start.strftime('%B %Y')

    @property
    def is_current(self):
        today = date.today()
        return self.period_start <= today <= self.period_end


class FollowUpRule(db.Model):
    __tablename__ = 'followup_rules'

    id = db.Column(db.Integer, primary_key=True)
    stage = db.Column(db.String(50), nullable=False, unique=True)
    days_threshold = db.Column(db.Integer, nullable=False)
    enabled = db.Column(db.Boolean, default=True)


class TimeEntry(db.Model):
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    datum = db.Column(db.Date, nullable=False)
    dauer_minuten = db.Column(db.Integer, default=0)
    taetigkeit = db.Column(db.String(200), nullable=False)
    notiz = db.Column(db.Text, nullable=True)
    timer_start = db.Column(db.DateTime, nullable=True)
    billed_document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    recurring_days = db.Column(db.Integer, nullable=True)
    last_recurred = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    billed_document = db.relationship('Document', lazy=True)

    @property
    def is_billed(self):
        return self.billed_document_id is not None

    @property
    def dauer_display(self):
        h = self.dauer_minuten // 60
        m = self.dauer_minuten % 60
        return f'{h}:{m:02d}'

    @property
    def is_timer_running(self):
        return self.timer_start is not None


class WorkDay(db.Model):

    __tablename__ = 'work_days'

    datum = db.Column(db.Date, primary_key=True)
    minuten = db.Column(db.Integer, nullable=False, default=0)
    notiz = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    @property
    def dauer_display(self):
        h = self.minuten // 60
        m = self.minuten % 60
        return f'{h}:{m:02d}'


PAYMENT_TYPES = [
    ('setup', 'Einmalig (Setup)'),
    ('recurring', 'Laufend (monatlich)'),
    ('milestone', 'Meilenstein'),
]

PAYMENT_STATUSES = [
    ('pending', 'Offen'),
    ('received', 'Eingegangen'),
    ('cancelled', 'Storniert'),
]


class ExpectedPayment(db.Model):
    __tablename__ = 'expected_payments'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    label = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expected_date = db.Column(db.Date, nullable=False)
    payment_type = db.Column(db.String(20), nullable=False, default='setup')
    interval_months = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    received_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    @property
    def status_label(self):
        return dict(PAYMENT_STATUSES).get(self.status, self.status)

    @property
    def type_label(self):
        return dict(PAYMENT_TYPES).get(self.payment_type, self.payment_type)


class NumberSequence(db.Model):
    __tablename__ = 'number_sequences'

    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(10), unique=True, nullable=False)
    next_number = db.Column(db.Integer, nullable=False, default=1)
    padding = db.Column(db.Integer, nullable=False, default=5)

    def generate(self):
        number = f"{self.prefix}-{str(self.next_number).zfill(self.padding)}"
        self.next_number += 1
        return number


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    doc_type = db.Column(db.String(20), nullable=False)
    number = db.Column(db.String(50), unique=True, nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft')
    date = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    sent_date = db.Column(db.Date, nullable=True)
    payment_date = db.Column(db.Date, nullable=True)
    conditions_text = db.Column(db.Text, nullable=True)
    service_period = db.Column(db.Text, nullable=True)
    payment_term_days = db.Column(db.Integer, nullable=False, default=14)
    internal_notes = db.Column(db.Text, nullable=True)
    discount_type = db.Column(db.String(20), nullable=True)
    discount_value = db.Column(db.Numeric(10, 2), nullable=True)
    source_document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    dunning_level = db.Column(db.Integer, default=0)
    dunning_last_sent = db.Column(db.Date, nullable=True)
    pdf_cache = db.Column(db.LargeBinary, nullable=True)
    pdf_cached_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    groups = db.relationship('LineItemGroup', backref='document', lazy=True,
                               cascade='all, delete-orphan',
                               order_by='LineItemGroup.position')
    source_document = db.relationship('Document', remote_side=[id],
                                        backref=db.backref('derived_documents', lazy=True))

    @property
    def total_onetime_net(self):
        return round(sum(item.line_total for g in self.groups for item in g.items
                   if item.billing_type == 'onetime'), 2)

    @property
    def total_recurring_net(self):
        return round(sum(item.line_total for g in self.groups for item in g.items
                   if item.billing_type == 'recurring'), 2)

    @property
    def total_onetime_vat(self):
        return round(sum(item.line_vat for g in self.groups for item in g.items
                   if item.billing_type == 'onetime'), 2)

    @property
    def total_recurring_vat(self):
        return round(sum(item.line_vat for g in self.groups for item in g.items
                   if item.billing_type == 'recurring'), 2)

    @property
    def total_onetime_gross(self):
        return round(self.total_onetime_net + self.total_onetime_vat, 2)

    @property
    def total_recurring_gross(self):
        return round(self.total_recurring_net + self.total_recurring_vat, 2)

    @property
    def total_net(self):
        return round(self.total_onetime_net + self.total_recurring_net, 2)

    @property
    def total_vat(self):
        return round(self.total_onetime_vat + self.total_recurring_vat, 2)

    @property
    def total_gross(self):
        return round(self.total_net + self.total_vat, 2)

    @property
    def vat_rate_label(self):
        rates = {float(item.vat_rate) for g in self.groups for item in g.items}
        if len(rates) == 1:
            return f'{rates.pop():g}% '
        return ''

    @property
    def discount_amount(self):
        if not self.discount_value or float(self.discount_value) <= 0:
            return 0
        if self.discount_type == 'percent':
            return round(self.total_net * float(self.discount_value) / 100, 2)
        return round(float(self.discount_value), 2)

    @property
    def total_after_discount_net(self):
        return round(max(0, self.total_net - self.discount_amount), 2)

    @property
    def total_after_discount_vat(self):
        net = self.total_net
        if net == 0:
            return 0
        return round(self.total_after_discount_net * self.total_vat / net, 2)

    @property
    def total_after_discount_gross(self):
        return round(self.total_after_discount_net + self.total_after_discount_vat, 2)

    @property
    def has_discount(self):
        return self.discount_value is not None and float(self.discount_value) > 0

    @property
    def discount_onetime_amount(self):
        if not self.has_discount or self.total_net == 0:
            return 0
        return round(self.discount_amount * self.total_onetime_net / self.total_net, 2)

    @property
    def discount_recurring_amount(self):
        if not self.has_discount or self.total_net == 0:
            return 0
        return round(self.discount_amount * self.total_recurring_net / self.total_net, 2)

    @property
    def total_onetime_after_discount_net(self):
        return round(max(0, self.total_onetime_net - self.discount_onetime_amount), 2)

    @property
    def total_recurring_after_discount_net(self):
        return round(max(0, self.total_recurring_net - self.discount_recurring_amount), 2)

    @property
    def total_onetime_after_discount_vat(self):
        return round(self.total_onetime_after_discount_net * 0.2, 2)

    @property
    def total_recurring_after_discount_vat(self):
        return round(self.total_recurring_after_discount_net * 0.2, 2)

    @property
    def total_onetime_after_discount_gross(self):
        return round(self.total_onetime_after_discount_net + self.total_onetime_after_discount_vat, 2)

    @property
    def total_recurring_after_discount_gross(self):
        return round(self.total_recurring_after_discount_net + self.total_recurring_after_discount_vat, 2)

    @property
    def has_recurring(self):
        return any(item.billing_type == 'recurring'
                   for g in self.groups for item in g.items)

    @property
    def status_label(self):
        statuses = dict(QUOTE_STATUSES) if self.doc_type == 'quote' else dict(INVOICE_STATUSES)
        return statuses.get(self.status, self.status)

    @property
    def type_label(self):
        return 'Angebot' if self.doc_type == 'quote' else 'Rechnung'


class LineItemGroup(db.Model):
    __tablename__ = 'line_item_groups'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    items = db.relationship('LineItem', backref='group', lazy=True,
                              cascade='all, delete-orphan',
                              order_by='LineItem.position')


class LineItem(db.Model):
    __tablename__ = 'line_items'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('line_item_groups.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit = db.Column(db.String(50), nullable=False, default='Einmalig')
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=20.0)
    billing_type = db.Column(db.String(20), nullable=False, default='onetime')

    @property
    def line_total(self):
        return round(float(self.quantity) * float(self.unit_price), 2)

    @property
    def line_vat(self):
        return round(self.line_total * float(self.vat_rate) / 100, 2)

    @property
    def line_gross(self):
        return round(self.line_total + self.line_vat, 2)


class ServiceTemplate(db.Model):
    __tablename__ = 'service_templates'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    unit = db.Column(db.String(50), nullable=False, default='Einmalig')
    billing_type = db.Column(db.String(20), nullable=False, default='onetime')
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, default=True)
    use_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class ConditionsTemplate(db.Model):
    __tablename__ = 'conditions_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    text = db.Column(db.Text, nullable=False)
    payment_term_days = db.Column(db.Integer, nullable=False, default=14)
    position = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)


class GroupTemplate(db.Model):
    __tablename__ = 'group_templates'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    items = db.relationship('GroupTemplateItem', backref='group_template', lazy=True,
                              cascade='all, delete-orphan',
                              order_by='GroupTemplateItem.position')


class GroupTemplateItem(db.Model):
    __tablename__ = 'group_template_items'

    id = db.Column(db.Integer, primary_key=True)
    group_template_id = db.Column(db.Integer, db.ForeignKey('group_templates.id'), nullable=False)
    service_template_id = db.Column(db.Integer, db.ForeignKey('service_templates.id'), nullable=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit = db.Column(db.String(50), nullable=False, default='Einmalig')
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    billing_type = db.Column(db.String(20), nullable=False, default='onetime')
    position = db.Column(db.Integer, nullable=False, default=0)

    service_template = db.relationship('ServiceTemplate', lazy=True)


class CompanySettings(db.Model):
    __tablename__ = 'company_settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False, default='')

    DEFAULTS = {
        'company_name': 'Musterwerkstatt e.U.',
        'street': 'Hauptplatz 1',
        'zip_city': '4020 Linz',
        'zip_city_short': '4020 Linz',
        'tax_number': '00 000/0000',
        'company_register': 'FN 000000 a',
        'phone': '+43 000 0000000',
        'email': 'office@musterwerkstatt.example',
        'website': 'www.musterwerkstatt.example',
        'bank_name': '',
        'bank_account_holder': 'Max Mustermann',
        'iban': 'AT00 0000 0000 0000 0000',
        'bic': '',
        'owner_name': 'Max Mustermann',
        'weekly_hours_target': '40',
        'mandate_kapazitaet_wochenstunden': '20',
        'default_hourly_rate': '100',
        'umsatz_plan_jahr': '',
        'dashboard_hidden_widgets': '',
        'uid': '',
        'email_signature': '',
        'content_autopost_enabled': '0',
        'content_outbox_enabled': '0',
    }

    @classmethod
    def get(cls, key):
        row = cls.query.get(key)
        if row:
            return row.value
        return cls.DEFAULTS.get(key, '')

    @classmethod
    def get_all(cls):
        result = dict(cls.DEFAULTS)
        for row in cls.query.all():
            result[row.key] = row.value
        return result


class Retainer(db.Model):
    __tablename__ = 'retainers'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False)
    monthly_fee = db.Column(db.Float, nullable=False)
    monthly_hours = db.Column(db.Float, nullable=False)
    billing_interval_months = db.Column(db.Integer, nullable=False, default=6)
    hourly_rate = db.Column(db.Float, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)
    last_billed_date = db.Column(db.Date, nullable=True)
    last_fee_period = db.Column(db.String(7), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    contact = db.relationship('Contact', backref=db.backref('retainers', lazy=True))

    @property
    def effective_hourly_rate(self):
        return self.hourly_rate or (self.contact.hourly_rate if self.contact else 0) or 0


class DocumentStatusLog(db.Model):
    __tablename__ = 'document_status_log'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=False)
    changed_at = db.Column(db.DateTime, default=utcnow_naive)
    note = db.Column(db.Text, nullable=True)

    document = db.relationship('Document', backref=db.backref('status_log', lazy=True,
                               cascade='all, delete-orphan',
                               order_by='DocumentStatusLog.changed_at.desc()'))



class WikiPage(db.Model):
    __tablename__ = 'wiki_pages'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), unique=True, nullable=False)
    content = db.Column(db.Text, default='')
    category = db.Column(db.String(100), nullable=True)
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    @staticmethod
    def slugify(text):
        import re
        slug = text.lower().strip()
        slug = re.sub(r'[äÄ]', 'ae', slug)
        slug = re.sub(r'[öÖ]', 'oe', slug)
        slug = re.sub(r'[üÜ]', 'ue', slug)
        slug = re.sub(r'[ß]', 'ss', slug)
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        return slug.strip('-')


LEISTUNGSBEREICHE = {
    '': '—',
    '00': '00 Leistungen & Produkte',
    '01': '01 Webdesign',
    '02': '02 Technisches Fundament',
    '03': '03 Tracking',
    '04': '04 SEO',
    '05': '05 GEO',
    '06': '06 Google Ads',
    '07': '07 Google Grants',
    '08': '08 Email Marketing',
    '09': '09 Social Media',
}

ENTRY_TYPES = {
    'skill': 'Skill',
    'agent': 'Agent',
    'command': 'Command',
    'script': 'Script',
    'workflow': 'Workflow',
    'template': 'Vorlage',
}

ENTRY_STATUSES = {
    'active': 'Aktiv',
    'draft': 'Entwurf',
    'deprecated': 'Veraltet',
}



ACCOUNT_STATUSES = [
    ('active', 'Aktiv'),
    ('pending', 'Ausstehend'),
    ('needs_client', 'Vom Kunden'),
    ('inactive', 'Inaktiv'),
]

ACCOUNT_CATEGORIES = [
    ('tracking', 'Tracking & Analyse'),
    ('seo', 'SEO & Sichtbarkeit'),
    ('ads', 'Bezahlte Werbung'),
    ('social', 'Social Media'),
    ('reporting', 'Reporting'),
    ('cms', 'Website'),
    ('email', 'E-Mail Marketing'),
    ('other', 'Sonstiges'),
]


class AccountToolType(db.Model):
    __tablename__ = 'account_tool_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='other')
    default_url = db.Column(db.String(300), nullable=True)
    sort_order = db.Column(db.Integer, default=100)

    accounts = db.relationship('CustomerAccount', backref='tool_type', lazy=True)

    def __repr__(self):
        return f'<AccountToolType {self.short_name}>'


class CustomerAccount(db.Model):
    __tablename__ = 'customer_accounts'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    tool_type_id = db.Column(db.Integer, db.ForeignKey('account_tool_types.id'), nullable=False)
    account_id = db.Column(db.String(200), nullable=True)
    login_email = db.Column(db.String(200), nullable=True)
    login_password = db.Column(db.String(300), nullable=True)
    client_login_email = db.Column(db.String(200), nullable=True)
    client_login_password = db.Column(db.String(300), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    done = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    def __repr__(self):
        return f'<CustomerAccount {self.tool_type.short_name if self.tool_type else "?"} for contact {self.contact_id}>'


class WikiEntry(db.Model):
    __tablename__ = 'wiki_entries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    entry_type = db.Column(db.String(20), nullable=False, default='skill')
    description = db.Column(db.Text, default='')
    trigger_phrases = db.Column(db.Text, default='')
    example_call = db.Column(db.Text, default='')
    leistungsbereich = db.Column(db.String(5), default='')
    file_path = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class WikiFileLink(db.Model):
    __tablename__ = 'wiki_file_links'

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(300), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, default='')
    wiki_page_id = db.Column(db.Integer, db.ForeignKey('wiki_pages.id'), nullable=True)
    wiki_entry_id = db.Column(db.Integer, db.ForeignKey('wiki_entries.id'), nullable=True)

    page = db.relationship('WikiPage', backref=db.backref('file_links', lazy=True, cascade='all, delete-orphan'))
    entry = db.relationship('WikiEntry', backref=db.backref('file_links', lazy=True, cascade='all, delete-orphan'))



class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    gmbh_account_code = db.Column(db.String(10), nullable=True)
    ear_group = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=100, nullable=False)

    def __repr__(self):
        return f'<ExpenseCategory {self.code}>'


class IncomingInvoice(db.Model):
    __tablename__ = 'incoming_invoices'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    expense_category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)

    external_invoice_number = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(500), nullable=False)

    invoice_date = db.Column(db.Date, nullable=False)
    delivery_date = db.Column(db.Date, nullable=True)
    posting_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    payment_date = db.Column(db.Date, nullable=True)

    net_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=20)
    vat_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    gross_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    vat_exemption_reason = db.Column(db.String(200), nullable=True)
    is_vat_deductible = db.Column(db.Boolean, default=True, nullable=False)

    payment_method = db.Column(db.String(30), nullable=True)
    document_file_path = db.Column(db.String(500), nullable=True)
    beleg_status = db.Column(db.String(20), nullable=False, default='fehlt')
    status = db.Column(db.String(20), nullable=False, default='open')

    internal_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('supplier_id', 'external_invoice_number', name='uq_supplier_external_invoice'),
        db.Index('idx_incoming_supplier', 'supplier_id'),
        db.Index('idx_incoming_posting_date', 'posting_date'),
        db.Index('idx_incoming_category', 'expense_category_id'),
    )

    supplier = db.relationship('Contact', backref=db.backref('incoming_invoices', lazy=True,
                                                              order_by='IncomingInvoice.invoice_date.desc()'))
    category = db.relationship('ExpenseCategory', backref=db.backref('invoices', lazy=True))
    line_items = db.relationship('IncomingLineItem', backref='invoice', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='IncomingLineItem.position')

    @property
    def is_paid(self):
        return self.payment_date is not None

    @property
    def is_overdue(self):
        if self.is_paid or self.status == 'cancelled':
            return False
        if not self.due_date:
            return False
        return self.due_date < date.today()

    @property
    def vat_deductible_amount(self):
        return float(self.vat_amount) if self.is_vat_deductible else 0.0

    @property
    def status_label(self):
        if self.is_overdue:
            return 'Überfällig'
        return dict(INCOMING_INVOICE_STATUSES).get(self.status, self.status)

    @property
    def beleg_status_label(self):
        return dict(BELEG_STATUSES).get(self.beleg_status, self.beleg_status)

    @property
    def has_pdf(self):
        return bool(self.document_file_path)

    def __repr__(self):
        return f'<IncomingInvoice {self.number}>'


class IncomingLineItem(db.Model):
    __tablename__ = 'incoming_line_items'

    id = db.Column(db.Integer, primary_key=True)
    incoming_invoice_id = db.Column(db.Integer,
                                     db.ForeignKey('incoming_invoices.id', ondelete='CASCADE'),
                                     nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    net_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    vat_rate = db.Column(db.Numeric(5, 2), nullable=False, default=20)
    vat_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    expense_category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)

    category = db.relationship('ExpenseCategory')



BANK_MATCH_STATUSES = [
    ('unmatched', 'Kein Match'),
    ('suggested', 'Vorschlag offen'),
    ('confirmed', 'Bestätigt'),
    ('ignored', 'Kein Beleg nötig'),
]


class BankImport(db.Model):
    __tablename__ = 'bank_imports'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    schema_name = db.Column(db.String(50), nullable=True)
    imported_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    new_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    period_from = db.Column(db.Date, nullable=True)
    period_to = db.Column(db.Date, nullable=True)

    transactions = db.relationship('BankTransaction', backref='bank_import', lazy=True,
                                     order_by='BankTransaction.booking_date')

    def __repr__(self):
        return f'<BankImport {self.filename} {self.new_count}/{self.row_count}>'


class BankTransaction(db.Model):
    __tablename__ = 'bank_transactions'

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey('bank_imports.id'), nullable=False)

    booking_date = db.Column(db.Date, nullable=False)
    value_date = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='EUR')
    foreign_amount = db.Column(db.Numeric(12, 2), nullable=True)
    foreign_currency = db.Column(db.String(3), nullable=True)

    partner_name = db.Column(db.String(300), nullable=True)
    partner_iban = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.Text, nullable=True)
    tx_type = db.Column(db.String(50), nullable=True)

    row_hash = db.Column(db.String(64), nullable=False, unique=True)

    match_status = db.Column(db.String(20), nullable=False, default='unmatched')
    matched_document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    matched_incoming_invoice_id = db.Column(db.Integer, db.ForeignKey('incoming_invoices.id'),
                                              nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)

    __table_args__ = (
        db.Index('idx_bank_tx_booking_date', 'booking_date'),
        db.Index('idx_bank_tx_match_status', 'match_status'),
        db.Index('idx_bank_tx_import', 'import_id'),
    )

    matched_document = db.relationship('Document',
                                         backref=db.backref('bank_transactions', lazy=True))
    matched_incoming_invoice = db.relationship('IncomingInvoice',
                                                 backref=db.backref('bank_transactions', lazy=True))

    @property
    def direction(self):
        return 'in' if (self.amount or 0) >= 0 else 'out'

    @property
    def abs_amount(self):
        return abs(float(self.amount or 0))

    @property
    def match_status_label(self):
        return dict(BANK_MATCH_STATUSES).get(self.match_status, self.match_status)

    @property
    def is_open(self):
        return self.match_status in ('unmatched', 'suggested')

    def __repr__(self):
        return f'<BankTransaction {self.booking_date} {self.amount} {self.match_status}>'

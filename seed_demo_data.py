import os
import sys
import random
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from models import db as _db
from database import init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DB_PATH = os.path.join(BASE_DIR, 'data', 'demo.db')

demo_app = Flask(__name__)
demo_app.config['SECRET_KEY'] = 'demo-secret-key'
demo_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DEMO_DB_PATH}'
demo_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(demo_app)

from models import (
    db, Contact, Interaction, StatusChange, TimeEntry, Task, TaskComment,
    task_tags, Document, LineItemGroup, LineItem, ExpectedPayment, SalesGoal,
    FollowUpRule, CompanySettings, Retainer, NumberSequence,
    PIPELINE_STAGES, DEAL_PROBABILITY_DEFAULTS,
)

app = demo_app


DEMO_CONTACTS = [
    ('Bergwerk Kulturverein', 'Verein', 'Anna', 'Steiner', 'Frau', 'Obfrau', 'a.steiner@bergwerk-kultur.example', '+43 732 123456', 'bergwerk-kultur.example', 'Linz', '4020', 'Hauptplatz 12', 'Oberösterreich', 'bildung', 'website', True, 'Deutsch'),
    ('Sonnental Tischlerei GmbH', 'GmbH', 'Thomas', 'Gruber', 'Herr', 'Geschäftsführer', 't.gruber@sonnental-tischlerei.example', '+43 7252 88110', 'sonnental-tischlerei.example', 'Steyr', '4000', 'Industriestraße 7', 'Oberösterreich', 'industrie', 'empfehlung', False, 'Deutsch'),
    ('Grüne Welle Umweltverein', 'Verein', 'Lisa', 'Hofer', 'Frau', 'Geschäftsführerin', 'l.hofer@gruene-welle.example', '+43 732 445566', 'gruene-welle.example', 'Linz', '4020', 'Umweltgasse 3', 'Oberösterreich', 'other', 'email', True, 'Deutsch'),
    ('Alpenblick Hotels KG', 'KG', 'Markus', 'Pichler', 'Herr', 'Marketing Leiter', 'm.pichler@alpenblick-hotels.example', '+43 7612 34567', 'alpenblick-hotels.example', 'Bad Ischl', '4820', 'Seestraße 22', 'Oberösterreich', 'handel', 'linkedin', False, 'Deutsch'),
    ('Donau Digital e.U.', 'e.U.', 'Sandra', 'Mayr', 'Frau', 'Inhaberin', 's.mayr@donau-digital.example', '+43 732 998877', 'donau-digital.example', 'Linz', '4040', 'Digitalweg 5', 'Oberösterreich', 'saas', 'messe', False, 'Deutsch'),
    ('Werkstadt Jugendhilfe', 'Verein', 'Michael', 'Bauer', 'Herr', 'Projektleiter', 'm.bauer@werkstadt-jugend.example', '+43 732 112233', 'werkstadt-jugend.example', 'Linz', '4020', 'Jugendstraße 9', 'Oberösterreich', 'bildung', 'cold_call', True, 'Deutsch'),
    ('Mühlviertel Keramik', 'GmbH', 'Eva', 'Wimmer', 'Frau', 'Inhaberin', 'e.wimmer@mv-keramik.example', '+43 7942 55443', 'mv-keramik.example', 'Freistadt', '4240', 'Töpferweg 14', 'Oberösterreich', 'handel', 'website', False, 'Deutsch'),
    ('Stadtteil Sozialverein Wels', 'Verein', 'Johannes', 'Lang', 'Herr', 'Obmann', 'j.lang@stadtteil-wels.example', '+43 7242 66778', 'stadtteil-wels.example', 'Wels', '4600', 'Vereinsgasse 1', 'Oberösterreich', 'gesundheit', 'empfehlung', True, 'Deutsch'),
    ('Panorama Fotografie', 'e.U.', 'Katharina', 'Eder', 'Frau', 'Fotografin', 'k.eder@panorama-foto.example', '+43 664 1234567', 'panorama-foto.example', 'Gmunden', '4810', 'Seeuferstraße 8', 'Oberösterreich', 'other', 'website', False, 'Deutsch'),
    ('Brückenbau Consulting', 'GmbH', 'Stefan', 'Huber', 'Herr', 'Partner', 's.huber@brueckenbau.example', '+43 732 776655', 'brueckenbau.example', 'Linz', '4020', 'Beratungsplatz 4', 'Oberösterreich', 'beratung', 'linkedin', False, 'Deutsch'),
    ('Lebenshilfe Innviertel', 'Verein', 'Maria', 'Fuchs', 'Frau', 'Geschäftsführerin', 'm.fuchs@lebenshilfe-inn.example', '+43 7722 33445', 'lebenshilfe-inn.example', 'Ried im Innkreis', '4910', 'Hilfestraße 6', 'Oberösterreich', 'gesundheit', 'email', True, 'Deutsch'),
    ('Backhaus Tradition OG', 'OG', 'Franz', 'Moser', 'Herr', 'Bäckermeister', 'f.moser@backhaus-tradition.example', '+43 7582 11223', 'backhaus-tradition.example', 'Vöcklabruck', '4840', 'Bäckergasse 19', 'Oberösterreich', 'handel', 'empfehlung', False, 'Deutsch'),
    ('Zukunft Bildung OÖ', 'Verein', 'Petra', 'Schuster', 'Frau', 'Vorstand', 'p.schuster@zukunft-bildung.example', '+43 732 554433', 'zukunft-bildung.example', 'Linz', '4020', 'Bildungsring 11', 'Oberösterreich', 'bildung', 'messe', True, 'Deutsch'),
    ('Seenland IT Solutions', 'GmbH', 'Daniel', 'Wolf', 'Herr', 'CTO', 'd.wolf@seenland-it.example', '+43 7672 88990', 'seenland-it.example', 'Vöcklabruck', '4840', 'Technikweg 2', 'Oberösterreich', 'saas', 'linkedin', False, 'Deutsch'),
    ('Tierheim Traunviertel', 'Verein', 'Sabine', 'Berger', 'Frau', 'Leiterin', 's.berger@tierheim-tv.example', '+43 7242 44556', 'tierheim-tv.example', 'Wels', '4600', 'Tierfreundeweg 7', 'Oberösterreich', 'other', 'website', True, 'Deutsch'),
    ('Atelier Lichtblick', 'e.U.', 'Nina', 'Reiter', 'Frau', 'Designerin', 'n.reiter@atelier-lichtblick.example', '+43 664 9876543', 'atelier-lichtblick.example', 'Linz', '4020', 'Kreativstraße 15', 'Oberösterreich', 'other', 'website', False, 'Deutsch'),
    ('Holzweg Möbel GmbH', 'GmbH', 'Georg', 'Haas', 'Herr', 'Geschäftsführer', 'g.haas@holzweg-moebel.example', '+43 7262 55667', 'holzweg-moebel.example', 'Enns', '4470', 'Holzstraße 3', 'Oberösterreich', 'handel', 'cold_call', False, 'Deutsch'),
    ('Flüchtlingshilfe OÖ', 'Verein', 'Clara', 'Schwarz', 'Frau', 'Koordinatorin', 'c.schwarz@fluechtlingshilfe-ooe.example', '+43 732 667788', 'fluechtlingshilfe-ooe.example', 'Linz', '4020', 'Solidaritätsplatz 2', 'Oberösterreich', 'other', 'email', True, 'Deutsch'),
    ('Gasthaus Goldener Hirsch', 'e.U.', 'Robert', 'Kern', 'Herr', 'Wirt', 'r.kern@goldener-hirsch.example', '+43 7583 22334', 'goldener-hirsch.example', 'Attnang-Puchheim', '4800', 'Marktplatz 1', 'Oberösterreich', 'handel', 'empfehlung', False, 'Deutsch'),
    ('TechForGood Foundation', 'Stiftung', 'Dominik', 'Roth', 'Herr', 'Direktor', 'd.roth@techforgood.example', '+43 732 889900', 'techforgood.example', 'Linz', '4020', 'Innovationspark 8', 'Oberösterreich', 'saas', 'linkedin', True, 'Deutsch'),
    ('Blumengarten Deko', 'e.U.', 'Claudia', 'Fischer', 'Frau', 'Inhaberin', 'c.fischer@blumengarten-deko.example', '+43 664 5554433', 'blumengarten-deko.example', 'Wels', '4600', 'Gartenstraße 20', 'Oberösterreich', 'handel', 'website', False, 'Deutsch'),
    ('Seniorenresidenz Am Park', 'GmbH', 'Heinrich', 'Wagner', 'Herr', 'Heimleiter', 'h.wagner@residenz-ampark.example', '+43 7242 77889', 'residenz-ampark.example', 'Wels', '4600', 'Parkallee 5', 'Oberösterreich', 'gesundheit', 'messe', False, 'Deutsch'),
    ('Kulturbrücke International', 'Verein', 'Yasmin', 'Özkan', 'Frau', 'Projektleiterin', 'y.oezkan@kulturbruecke.example', '+43 732 334455', 'kulturbruecke.example', 'Linz', '4020', 'Kulturweg 13', 'Oberösterreich', 'bildung', 'email', True, 'Deutsch'),
    ('Motorrad Maier', 'GmbH', 'Christian', 'Maier', 'Herr', 'Inhaber', 'c.maier@motorrad-maier.example', '+43 7252 11445', 'motorrad-maier.example', 'Steyr', '4000', 'Motorradweg 9', 'Oberösterreich', 'handel', 'cold_call', False, 'Deutsch'),
    ('Naturfreunde Salzkammergut', 'Verein', 'Brigitte', 'Koller', 'Frau', 'Obfrau', 'b.koller@naturfreunde-sk.example', '+43 6132 22556', 'naturfreunde-sk.example', 'Bad Ischl', '4820', 'Wanderweg 4', 'Oberösterreich', 'other', 'website', True, 'Deutsch'),
    ('Dachstein Bau GmbH', 'GmbH', 'Wolfgang', 'Aigner', 'Herr', 'Bauleiter', 'w.aigner@dachstein-bau.example', '+43 7612 99887', 'dachstein-bau.example', 'Bad Ischl', '4820', 'Baustraße 16', 'Oberösterreich', 'industrie', 'empfehlung', False, 'Deutsch'),
    ('Elterninitiative Wels', 'Verein', 'Andrea', 'Müller', 'Frau', 'Sprecherin', 'a.mueller@elterninitiative-wels.example', '+43 7242 55667', 'elterninitiative-wels.example', 'Wels', '4600', 'Elterngasse 8', 'Oberösterreich', 'bildung', 'website', True, 'Deutsch'),
    ('Sportpark Arena', 'GmbH', 'Max', 'Stadler', 'Herr', 'Betriebsleiter', 'l.stadler@sportpark-arena.example', '+43 7252 66778', 'sportpark-arena.example', 'Steyr', '4000', 'Sportplatzweg 3', 'Oberösterreich', 'other', 'linkedin', False, 'Deutsch'),
    ('Lernwerkstatt Plus', 'e.U.', 'Sonja', 'Neumann', 'Frau', 'Pädagogin', 's.neumann@lernwerkstatt-plus.example', '+43 732 223344', 'lernwerkstatt-plus.example', 'Linz', '4020', 'Lernstraße 6', 'Oberösterreich', 'bildung', 'empfehlung', False, 'Deutsch'),
    ('Windkraft Oberösterreich', 'GmbH', 'Martin', 'Lehner', 'Herr', 'Projektmanager', 'm.lehner@windkraft-ooe.example', '+43 732 887766', 'windkraft-ooe.example', 'Linz', '4040', 'Energiepark 10', 'Oberösterreich', 'industrie', 'messe', False, 'Deutsch'),
]

PIPELINE_DISTRIBUTION = {
    'new': 4,
    'contacted': 5,
    'qualified': 4,
    'proposal': 4,
    'negotiation': 3,
    'won': 6,
    'lost': 2,
    'on_hold': 2,
}

DEAL_VALUES = {
    'new': (500, 3000),
    'contacted': (1000, 5000),
    'qualified': (2000, 8000),
    'proposal': (3000, 12000),
    'negotiation': (4000, 15000),
    'won': (2000, 20000),
    'lost': (1000, 8000),
    'on_hold': (1500, 6000),
}

INTERACTION_TYPES = ['Anruf', 'E-Mail', 'Meeting', 'LinkedIn', 'Notiz']
INTERACTION_NOTES = [
    'Erstgespräch geführt, Interesse an Website-Redesign',
    'Angebot per Mail gesendet',
    'Rückfragen zu SEO-Paket besprochen',
    'Follow-up Termin vereinbart für nächste Woche',
    'Google Ads Beratung gewünscht, Budget ca. 500€/Monat',
    'Sehr interessiert an Google Ad Grants, braucht Gemeinnützigkeits-Nachweis',
    'Tracking-Audit durchgeführt, GTM fehlt komplett',
    'Konkurrenzangebot liegt vor, Preis vergleichen',
    'Zufrieden mit bisheriger Arbeit, Retainer besprochen',
    'Website-Launch besprochen, Go-Live Mitte nächsten Monat',
    'Social Media Strategie vorgestellt',
    'Feedback zum Angebot: Budget passt, Umfang klären',
    'Rechnung bezahlt, Danke-Mail gesendet',
    'Neuer Ansprechpartner, Übergabe-Meeting',
    'Fördercheck durchgeführt, KMU.DIGITAL möglich',
]

TASK_DATA = [
    ('Website-Relaunch Konzept erstellen', 'in_arbeit', 'Kundenprojekt', 'hoch', 'l', 'hoch', 'Informationsarchitektur + Wireframes für Sonnental Tischlerei'),
    ('Google Ad Grants Antrag Bergwerk', 'todo', 'Kundenprojekt', 'hoch', 'm', 'hoch', 'Gemeinnützigkeits-Nachweis prüfen, Konto beantragen'),
    ('SEO-Audit Alpenblick Hotels', 'todo', 'Kundenprojekt', 'mittel', 'l', 'hoch', 'Technisches SEO + Content-Analyse, Lead-Absätze prüfen'),
    ('Monatsreport März erstellen', 'todo', 'Administration', 'mittel', 's', 'mittel', 'Google Ads + SEO Performance für alle Retainer-Kunden'),
    ('Blog-Artikel: KI im Marketing', 'backlog', 'Marketing', 'niedrig', 'm', 'mittel', 'Eigener Blog-Content für muster-agentur.example'),
    ('GTM-Setup Mühlviertel Keramik', 'in_arbeit', 'Kundenprojekt', 'hoch', 'm', 'hoch', 'GTM + GA4 + Borlabs, Standard-Events implementieren'),
    ('Angebot Holzweg Möbel nachfassen', 'todo', 'Vertrieb', 'hoch', 'xs', 'hoch', 'Angebot vor 10 Tagen gesendet, noch keine Rückmeldung'),
    ('Neuen Skill: SEO-Audit automatisieren', 'backlog', 'Entwicklung', 'niedrig', 'xl', 'hoch', 'Automatisierter OnPage-Audit als Claude Code Skill'),
    ('Social Media Plan Q2 Grüne Welle', 'review', 'Kundenprojekt', 'mittel', 'l', 'mittel', 'Content-Plan für Instagram + Facebook'),
    ('Stellwerk: Retainer-Abrechnung Feature', 'in_arbeit', 'Entwicklung', 'hoch', 'l', 'hoch', 'Automatische Rechnung aus Retainer-Guthaben'),
    ('Buchhaltung Februar abschließen', 'erledigt', 'Administration', 'mittel', 's', 'mittel', 'Belege sortieren, an Steuerberater senden'),
    ('Workshop-Konzept NPO-Digitalisierung', 'backlog', 'Marketing', 'mittel', 'xl', 'hoch', 'Halbtages-Workshop für NPOs, Fokus auf Google Ad Grants'),
    ('Meta Ads Kampagne Backhaus', 'todo', 'Kundenprojekt', 'hoch', 'l', 'hoch', 'Creatives erstellen, Zielgruppen definieren'),
    ('Keyword-Recherche Sportpark Arena', 'backlog', 'Kundenprojekt', 'mittel', 'm', 'mittel', 'Lokale Keywords + Konkurrenzanalyse'),
    ('Netzwerk-Event OÖ Digitalbranche', 'backlog', 'Netzwerk', 'niedrig', 's', 'mittel', 'Eigenes Event oder Kooperation mit WKO?'),
    ('Rechnung R-00004 überfällig, mahnen', 'todo', 'Administration', 'hoch', 'xs', 'mittel', 'Alpenblick Hotels, 14 Tage überfällig'),
    ('Landing Page Lernwerkstatt Plus', 'review', 'Kundenprojekt', 'mittel', 'l', 'hoch', 'Conversion-optimierte LP für Kursanmeldungen'),
    ('Google Ads Audit Motorrad Maier', 'erledigt', 'Kundenprojekt', 'hoch', 'm', 'hoch', 'Vollständiger 7-Ebenen Audit durchgeführt'),
]

TAETIGKEITEN_KONTAKT = [
    'onboarding', 'meetings', 'content', 'tracking', 'keywordrecherche',
    'setup_google_ads', 'menuefuehrung', 'angebotserstellung', 'anbahnung',
]
TAETIGKEITEN_ALLGEMEIN = [
    'akquise', 'netzwerken', 'interne_entwicklung', 'weiterbildung',
    'buchhaltung', 'marketing_eigenes',
]


DEMO_COMPANY_SETTINGS = {
    'company_name': 'Muster Digitalagentur e.U.',
    'street': 'Beispielstraße 42',
    'zip_city': '4020 Linz',
    'tax_number': 'ATU12345678',
    'company_register': 'FN 123456a',
    'phone': '+43 732 000000',
    'email': 'office@muster-agentur.example',
    'website': 'muster-agentur.example',
    'bank_name': 'Muster Sparkasse',
    'bank_account_holder': 'Muster Digitalagentur e.U.',
    'iban': 'AT12 3456 7890 1234 5678',
    'bic': 'MUSPAT2LXXX',
    'owner_name': 'Max Mustermann',
    'weekly_hours_target': '40',
    'default_hourly_rate': '100',
}


TODAY = date.today()

def random_date(days_back_min, days_back_max):
    delta = random.randint(days_back_min, days_back_max)
    return TODAY - timedelta(days=delta)

def random_datetime(days_back_min, days_back_max):
    d = random_date(days_back_min, days_back_max)
    return datetime(d.year, d.month, d.day, random.randint(8, 18), random.randint(0, 59))



def seed_company_settings():
    for key, value in DEMO_COMPANY_SETTINGS.items():
        existing = CompanySettings.query.filter_by(key=key).first()
        if existing:
            existing.value = value
        else:
            db.session.add(CompanySettings(key=key, value=value))
    db.session.commit()
    print(f"  OK Company settings ({len(DEMO_COMPANY_SETTINGS)} keys)")


def seed_contacts():
    contacts = []
    stage_index = 0
    stage_list = []

    for stage, count in PIPELINE_DISTRIBUTION.items():
        stage_list.extend([stage] * count)

    random.shuffle(stage_list)

    for i, (org, orgform, vn, nn, anrede, pos, mail, tel, web, stadt, plz, strasse, bl, branche, quelle, gemeinn, sprache) in enumerate(DEMO_CONTACTS):
        stage = stage_list[i] if i < len(stage_list) else 'new'
        prob = DEAL_PROBABILITY_DEFAULTS.get(stage, 10)
        low, high = DEAL_VALUES.get(stage, (1000, 5000))
        deal_val = round(random.randint(low, high) / 100) * 100

        created_days = {'new': (1, 14), 'contacted': (7, 30), 'qualified': (14, 60),
                        'proposal': (20, 75), 'negotiation': (30, 90),
                        'won': (60, 180), 'lost': (30, 120), 'on_hold': (20, 90)}
        d_min, d_max = created_days.get(stage, (1, 30))
        created = random_datetime(d_min, d_max)

        kontaktiert = None
        if stage not in ('new',):
            kontaktiert = (created + timedelta(days=random.randint(1, 5))).date()

        erinnerung = None
        erinnerungstext = None
        if stage in ('contacted', 'qualified', 'proposal', 'negotiation'):
            erinnerung = TODAY + timedelta(days=random.randint(-3, 7))
            reminders = ['Nachfassen', 'Termin vereinbaren', 'Angebot senden', 'Feedback einholen', 'Status prüfen']
            erinnerungstext = random.choice(reminders)

        tier = ''
        pipeline_phase = ''
        if stage == 'won':
            tier = random.choice(['starter', 'standard', 'premium'])
            pipeline_phase = random.choice(['2.3', '3.1', '4.1', '5.0'])

        customer_number = None
        if stage == 'won':
            customer_number = f'K-{(i + 1):05d}'

        lost_reason = None
        if stage == 'lost':
            lost_reason = random.choice(['budget', 'competitor', 'no_response', 'timing'])

        wie = random.choice(['E-Mail', 'Telefon', 'LinkedIn', 'Persönlich', 'Messe']) if kontaktiert else ''

        c = Contact(
            organisation=org, organisationsform=orgform,
            vorname=vn, nachname=nn, anrede=anrede, position=pos,
            mail_organisation=mail, telefon_organisation=tel, website=web,
            stadt=stadt, plz=plz, strasse=strasse, bundesland=bl,
            land='Österreich', branche=branche, quelle=quelle,
            gemeinnuetzig=gemeinn, sprache_1=sprache,
            status=stage, kontaktiert=kontaktiert, wie=wie,
            deal_value=deal_val, deal_probability=prob,
            erinnerung=erinnerung, erinnerungstext=erinnerungstext,
            tier=tier, pipeline_phase=pipeline_phase,
            customer_number=customer_number, lost_reason=lost_reason,
            prioritaet=random.choice(['A', 'B', 'C']),
            in_a_nutshell=f'{orgform} aus {stadt}, {branche.replace("_", " ").title()}',
            hourly_rate=100.0,
            created_at=created, updated_at=created,
        )
        db.session.add(c)
        db.session.flush()
        contacts.append(c)

    db.session.commit()
    print(f"  OK {len(contacts)} Kontakte erstellt")
    return contacts


def seed_interactions(contacts):
    count = 0
    for c in contacts:
        if c.status == 'new':
            n_interactions = random.randint(0, 1)
        elif c.status in ('contacted', 'on_hold'):
            n_interactions = random.randint(1, 3)
        else:
            n_interactions = random.randint(2, 5)

        for j in range(n_interactions):
            days_back = random.randint(1, 90)
            inter = Interaction(
                contact_id=c.id,
                datum=random_date(max(1, days_back - 10), days_back + 10),
                typ=random.choice(INTERACTION_TYPES),
                notiz=random.choice(INTERACTION_NOTES),
                created_at=random_datetime(days_back, days_back + 5),
            )
            db.session.add(inter)
            count += 1

    db.session.commit()
    print(f"  OK {count} Interaktionen")


def seed_status_changes(contacts):
    count = 0
    stage_order = ['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'won', 'lost']

    for c in contacts:
        if c.status == 'new':
            continue

        current_idx = stage_order.index(c.status) if c.status in stage_order else 1
        for i in range(current_idx):
            sc = StatusChange(
                contact_id=c.id,
                from_status=stage_order[i],
                to_status=stage_order[i + 1],
                deal_value_at_change=c.deal_value,
                changed_at=random_datetime(90 - (i * 15), 90 - (i * 15) + 10),
            )
            db.session.add(sc)
            count += 1

    db.session.commit()
    print(f"  OK {count} Status-Änderungen")


def seed_documents(contacts):
    doc_count = 0
    won_contacts = [c for c in contacts if c.status == 'won']
    proposal_contacts = [c for c in contacts if c.status in ('proposal', 'negotiation')]

    for c in proposal_contacts:
        doc = Document(
            contact_id=c.id, doc_type='quote',
            number=f'A-{(doc_count + 11):05d}',
            subject=f'Angebot: Digitale Sichtbarkeit für {c.organisation}',
            status=random.choice(['sent', 'sent', 'draft']),
            date=random_date(5, 30),
            valid_until=TODAY + timedelta(days=random.randint(7, 21)),
            payment_term_days=14,
            created_at=random_datetime(5, 30),
        )
        db.session.add(doc)
        db.session.flush()
        doc_count += 1

        grp = LineItemGroup(document_id=doc.id, position=1, title='Leistungen')
        db.session.add(grp)
        db.session.flush()

        items = [
            ('Website-Analyse & Konzept', 'Technische Analyse, Informationsarchitektur, Wireframes', 1, 'Pauschal', 600),
            ('SEO Grundoptimierung', 'OnPage-Optimierung, Meta-Tags, Schema Markup', 1, 'Pauschal', 400),
            ('Google Ads Setup', 'Kampagnenstruktur, Keywords, Anzeigentexte', 1, 'Pauschal', 800),
        ]
        for pos, (title, desc, qty, unit, price) in enumerate(random.sample(items, random.randint(2, 3)), 1):
            li = LineItem(group_id=grp.id, position=pos, title=title, description=desc,
                          quantity=qty, unit=unit, unit_price=price, vat_rate=20.0, billing_type='onetime')
            db.session.add(li)

    for c in won_contacts:
        n_invoices = random.randint(1, 3)
        for inv_i in range(n_invoices):
            inv_date = random_date(10 + inv_i * 30, 30 + inv_i * 30)
            status = random.choice(['paid', 'paid', 'paid', 'sent', 'overdue']) if inv_i < n_invoices - 1 else random.choice(['sent', 'paid', 'overdue'])

            doc = Document(
                contact_id=c.id, doc_type='invoice',
                number=f'R-{(doc_count + 6):05d}',
                subject=f'Rechnung: {random.choice(["Website-Projekt", "SEO-Paket", "Google Ads Betreuung", "Tracking-Setup", "Content-Erstellung"])}',
                status=status,
                date=inv_date,
                due_date=inv_date + timedelta(days=14),
                payment_date=(inv_date + timedelta(days=random.randint(5, 20))) if status == 'paid' else None,
                sent_date=inv_date if status != 'draft' else None,
                payment_term_days=14,
                created_at=datetime(inv_date.year, inv_date.month, inv_date.day, 10, 0),
            )
            db.session.add(doc)
            db.session.flush()
            doc_count += 1

            grp = LineItemGroup(document_id=doc.id, position=1, title='Leistungen')
            db.session.add(grp)
            db.session.flush()

            invoice_items = [
                ('Website-Erstellung', 'Responsive Website inkl. CMS', 1, 'Pauschal', random.choice([2000, 3000, 4000])),
                ('SEO Optimierung', 'OnPage + OffPage Analyse', 1, 'Pauschal', random.choice([400, 600, 800])),
                ('Google Ads Betreuung', 'Monatliche Kampagnen-Optimierung', 1, 'Monatlich', random.choice([300, 500, 700])),
                ('Tracking Setup', 'GTM + GA4 + Consent Mode', 1, 'Pauschal', 600),
                ('Content-Erstellung', '5 SEO-optimierte Seiten', 5, 'Seite', 200),
                ('Beratung', 'Strategische Digitalberatung', random.randint(2, 8), 'Stunde', 100),
            ]
            for pos, (title, desc, qty, unit, price) in enumerate(random.sample(invoice_items, random.randint(2, 4)), 1):
                li = LineItem(group_id=grp.id, position=pos, title=title, description=desc,
                              quantity=qty, unit=unit, unit_price=price, vat_rate=20.0,
                              billing_type='recurring' if 'Monatlich' in unit else 'onetime')
                db.session.add(li)

    db.session.commit()
    print(f"  OK {doc_count} Dokumente (Angebote + Rechnungen)")


def seed_time_entries(contacts):
    count = 0
    won_contacts = [c for c in contacts if c.status == 'won']
    active_contacts = [c for c in contacts if c.status in ('proposal', 'negotiation', 'qualified')]

    for c in (won_contacts + active_contacts):
        weeks = random.randint(2, 6)
        for w in range(weeks):
            entries_per_week = random.randint(1, 3)
            for _ in range(entries_per_week):
                d = TODAY - timedelta(weeks=w, days=random.randint(0, 4))
                te = TimeEntry(
                    contact_id=c.id,
                    datum=d,
                    dauer_minuten=random.choice([30, 45, 60, 90, 120, 180]),
                    taetigkeit=random.choice(TAETIGKEITEN_KONTAKT),
                    notiz=random.choice(['Kampagnen-Optimierung', 'Content erstellt', 'Meeting',
                                          'Technische Umsetzung', 'Reporting', 'Keyword-Analyse',
                                          'Setup & Konfiguration', 'Review & QA']),
                    created_at=datetime(d.year, d.month, d.day, random.randint(8, 17), 0),
                )
                db.session.add(te)
                count += 1

    for w in range(8):
        entries = random.randint(1, 3)
        for _ in range(entries):
            d = TODAY - timedelta(weeks=w, days=random.randint(0, 4))
            te = TimeEntry(
                contact_id=None,
                datum=d,
                dauer_minuten=random.choice([30, 60, 90, 120]),
                taetigkeit=random.choice(TAETIGKEITEN_ALLGEMEIN),
                notiz=random.choice(['Akquise-Mails', 'Weiterbildung', 'Buchhaltung',
                                      'Blog-Artikel', 'Tool-Entwicklung', 'Netzwerk-Event']),
                created_at=datetime(d.year, d.month, d.day, random.randint(8, 17), 0),
            )
            db.session.add(te)
            count += 1

    db.session.commit()
    print(f"  OK {count} Zeiteinträge")


def seed_tasks():
    from models import PRIORITY_SCORES, IMPACT_SCORES, EFFORT_SCORES
    count = 0
    for title, status, category, prio, effort, impact, desc in TASK_DATA:
        score = round((IMPACT_SCORES[impact] * PRIORITY_SCORES[prio]) / EFFORT_SCORES[effort], 1)
        t = Task(
            title=title, description=desc,
            status=status, category=category,
            priority=prio, effort=effort, impact=impact, score=score,
            due_date=TODAY + timedelta(days=random.randint(-5, 14)) if status in ('todo', 'in_arbeit') else None,
            position=count,
            created_at=random_datetime(5, 60),
        )
        if status == 'erledigt':
            t.completed_at = random_datetime(1, 10)
        db.session.add(t)
        db.session.flush()
        count += 1

        if random.random() > 0.5:
            comments = [
                'Kunde hat per Mail bestätigt',
                'Entwurf liegt vor, bitte Review',
                'Wartet auf Rückmeldung vom Kunden',
                'Erste Version fertig, Feinschliff fehlt noch',
                'Priorität erhöht wegen Deadline',
            ]
            tc = TaskComment(task_id=t.id, author='Max',
                             content=random.choice(comments),
                             created_at=random_datetime(1, 10))
            db.session.add(tc)

        tag_pool = ['dringend', 'kundenprojekt', 'intern', 'seo', 'ads', 'website', 'npo']
        for tag in random.sample(tag_pool, random.randint(1, 2)):
            try:
                db.session.execute(task_tags.insert().values(task_id=t.id, tag=tag))
                db.session.flush()
            except Exception:
                db.session.rollback()

    db.session.commit()
    print(f"  OK {count} Board-Tasks")


def seed_expected_payments(contacts):
    count = 0
    won_contacts = [c for c in contacts if c.status == 'won']

    for c in won_contacts:
        ep = ExpectedPayment(
            contact_id=c.id, label='Setup-Zahlung',
            amount=round(c.deal_value * 0.4, -1),
            expected_date=random_date(30, 90),
            payment_type='setup', status='received',
            received_date=random_date(20, 80),
        )
        db.session.add(ep)
        count += 1

        if random.random() > 0.3:
            ep2 = ExpectedPayment(
                contact_id=c.id, label='Monatliche Betreuung',
                amount=random.choice([300, 500, 700]),
                expected_date=TODAY + timedelta(days=random.randint(1, 28)),
                payment_type='recurring', interval_months=1,
                status='pending',
            )
            db.session.add(ep2)
            count += 1

    db.session.commit()
    print(f"  OK {count} Erwartete Zahlungen")


def seed_retainers(contacts):
    count = 0
    won_contacts = [c for c in contacts if c.status == 'won']

    for c in random.sample(won_contacts, min(3, len(won_contacts))):
        r = Retainer(
            contact_id=c.id,
            name=f'Retainer {c.organisation}',
            monthly_fee=random.choice([500, 700, 900]),
            monthly_hours=random.choice([5, 7, 10]),
            billing_interval_months=random.choice([3, 6]),
            start_date=random_date(60, 180),
            active=True,
        )
        db.session.add(r)
        count += 1

    db.session.commit()
    print(f"  OK {count} Retainer")


def seed_sales_goals():
    count = 0
    for m in range(6):
        d = TODAY.replace(day=1) - timedelta(days=30 * m)
        goal = SalesGoal(
            period_type='monthly',
            period_start=d.replace(day=1),
            target_amount=random.choice([6000, 7000, 8000, 9000, 10000]),
        )
        db.session.add(goal)
        count += 1

    db.session.commit()
    print(f"  OK {count} Sales Goals")


def seed_followup_rules():
    from models import FOLLOWUP_DEFAULTS
    count = 0
    for stage, days in FOLLOWUP_DEFAULTS.items():
        existing = FollowUpRule.query.filter_by(stage=stage).first()
        if not existing:
            db.session.add(FollowUpRule(stage=stage, days_threshold=days, enabled=True))
            count += 1
    db.session.commit()
    if count:
        print(f"  OK {count} Follow-up Regeln")



def wipe_demo_data():
    print("  Lösche bestehende Daten...")
    db.session.execute(task_tags.delete())
    for model in [TaskComment, Task, LineItem, LineItemGroup, Document,
                  Interaction, StatusChange, TimeEntry, ExpectedPayment, Retainer,
                  SalesGoal, FollowUpRule]:
        model.query.delete()
    Contact.query.delete()
    db.session.commit()

    for seq in NumberSequence.query.all():
        if seq.prefix == 'A':
            seq.next_number = 11
        elif seq.prefix == 'R':
            seq.next_number = 6
        elif seq.prefix == 'K':
            seq.next_number = 1
    db.session.commit()
    print("  OK Daten gelöscht")


def main():
    force = '--force' in sys.argv

    with app.app_context():
        existing = Contact.query.count()
        if existing > 0 and not force:
            print(f"[!]  {existing} Kontakte vorhanden. Verwende --force zum Überschreiben.")
            return

        if force and existing > 0:
            wipe_demo_data()

        print("\n[SEED] Stellwerk Demo-Daten werden erstellt...\n")

        seed_company_settings()
        contacts = seed_contacts()
        seed_interactions(contacts)
        seed_status_changes(contacts)
        seed_documents(contacts)
        seed_time_entries(contacts)
        seed_tasks()
        seed_expected_payments(contacts)
        seed_retainers(contacts)
        seed_sales_goals()
        seed_followup_rules()

        print(f"\n[OK] Demo-Daten erfolgreich erstellt!")
        print(f"   App starten: python start_demo.py")
        print(f"   Dann: http://localhost:5001\n")


if __name__ == '__main__':
    main()

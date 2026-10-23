import calendar as calendar_module
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy.orm import joinedload

from models import (
    db, Contact, ContentCalendarEntry, ContentTakt,
    CONTENT_CALENDAR_STAGES, CONTENT_PLATFORMS, CONTENT_TAKT_EINHEITEN,
)
import content_takt

content_calendar_bp = Blueprint('content_calendar_bp', __name__, url_prefix='')



def _outbox_withdraw(entry):
    if not entry.outbox_job:
        return None
    import content_outbox
    store = None
    try:
        store = content_outbox.default_store()
        content_outbox.withdraw(entry, store)
        return None
    except content_outbox.OutboxBusy as exc:
        db.session.commit()
        return str(exc)
    except Exception as exc:
        db.session.rollback()
        return (f"Cloud-Warteschlange nicht erreichbar ({type(exc).__name__}), Änderung NICHT "
                "gespeichert. Der Eintrag liegt weiter in der Cloud und wird zum Termin gepostet.")
    finally:
        if store is not None:
            store.close()


def _outbox_im_hintergrund():
    import subprocess
    import sys
    from pathlib import Path
    from flask import current_app
    from models import CompanySettings
    if current_app.testing or CompanySettings.get('content_outbox_enabled') != '1':
        return
    root = Path(__file__).resolve().parent.parent
    with open(root / 'data' / 'content_outbox.log', 'a', encoding='utf-8') as log:
        subprocess.Popen([sys.executable, str(root / 'content_outbox.py'), 'sync'], cwd=str(root),
                         stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _parse_datetime_local(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _customer_contacts():
    return Contact.query.filter_by(contact_type='customer', has_social_mandate=True).order_by(
        Contact.organisation, Contact.nachname).all()


def _form_contacts(current=None):
    contacts = _customer_contacts()
    if current and current.id not in {c.id for c in contacts}:
        contacts = [current] + contacts
    return contacts



@content_calendar_bp.route('/content-calendar')
def content_calendar():
    view = request.args.get('view', 'calendar')
    if view not in ('calendar', 'board', 'week'):
        view = 'calendar'
    today = date.today()
    year = request.args.get('year', type=int) or today.year
    month = request.args.get('month', type=int) or today.month
    contact_filter = request.args.get('contact_id', type=int)
    platform_filter = request.args.get('platform')

    base_query = ContentCalendarEntry.query.options(joinedload(ContentCalendarEntry.contact))
    if contact_filter:
        base_query = base_query.filter(ContentCalendarEntry.contact_id == contact_filter)
    if platform_filter:
        base_query = base_query.filter(ContentCalendarEntry.platform == platform_filter)

    context = dict(
        view=view, year=year, month=month,
        contact_filter=contact_filter, platform_filter=platform_filter,
        stages=CONTENT_CALENDAR_STAGES, platforms=CONTENT_PLATFORMS,
        contacts=_customer_contacts(), today=today,
    )

    from content_publisher import due_entries
    context['due_count'] = len(due_entries())

    takte, eintraege, ohne_takt = content_takt.lade(db.session.connection().connection, today)
    context['takt_luecken'] = len(content_takt.luecken(content_takt.abdeckung(takte, eintraege, today)))
    context['takt_ohne'] = len(ohne_takt)

    board_data = {}
    for stage_key, stage_label, stage_color in CONTENT_CALENDAR_STAGES:
        board_data[stage_key] = base_query.filter(
            ContentCalendarEntry.status == stage_key
        ).order_by(ContentCalendarEntry.scheduled_for).all()
    context['board_data'] = board_data

    first_weekday, days_in_month = calendar_module.monthrange(year, month)

    month_entries = base_query.filter(
        ContentCalendarEntry.scheduled_for >= datetime(year, month, 1),
        ContentCalendarEntry.scheduled_for < datetime(year, month, days_in_month) + timedelta(days=1)
    ).order_by(ContentCalendarEntry.scheduled_for).all()

    entries_by_day = defaultdict(list)
    for entry in month_entries:
        if entry.scheduled_for:
            entries_by_day[entry.scheduled_for.day].append(entry)

    weeks = []
    week = [None] * first_weekday
    for day in range(1, days_in_month + 1):
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week += [None] * (7 - len(week))
        weeks.append(week)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    wref = today
    wref_str = request.args.get('wref')
    if wref_str:
        try:
            wref = datetime.strptime(wref_str, '%Y-%m-%d').date()
        except ValueError:
            wref = today
    week_start = wref - timedelta(days=wref.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    week_end = week_start + timedelta(days=7)
    week_entries = base_query.filter(
        ContentCalendarEntry.scheduled_for >= datetime(week_start.year, week_start.month, week_start.day),
        ContentCalendarEntry.scheduled_for < datetime(week_end.year, week_end.month, week_end.day),
    ).order_by(ContentCalendarEntry.scheduled_for).all()
    week_entries_by_date = {d: [] for d in week_days}
    for entry in week_entries:
        if entry.scheduled_for and entry.scheduled_for.date() in week_entries_by_date:
            week_entries_by_date[entry.scheduled_for.date()].append(entry)

    undated_entries = base_query.filter(ContentCalendarEntry.scheduled_for.is_(None)).order_by(
        ContentCalendarEntry.status).all()
    month_count = sum(len(v) for v in entries_by_day.values())
    week_count = sum(len(v) for v in week_entries_by_date.values())

    context.update(dict(
        weeks=weeks, entries_by_day=entries_by_day,
        undated_entries=undated_entries, month_count=month_count, week_count=week_count,
        month_start=date(year, month, 1),
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        week_days=week_days, week_start=week_start, week_entries_by_date=week_entries_by_date,
        prev_wref=(week_start - timedelta(days=7)).isoformat(),
        next_wref=(week_start + timedelta(days=7)).isoformat(),
        today_date=today,
    ))
    return render_template('content_calendar.html', **context)



def _takt_aus_form(takt, form):
    contact_id = form.get('contact_id', type=int)
    if not contact_id:
        raise ValueError('Kunde fehlt')
    takt.contact_id = contact_id
    takt.platform = form.get('platform') or ''
    takt.anzahl = form.get('anzahl', type=int)
    takt.intervall = form.get('intervall', type=int)
    takt.einheit = form.get('einheit') or ''
    ab, bis = form.get('gueltig_ab') or None, form.get('gueltig_bis') or None
    takt.gueltig_ab = datetime.strptime(ab, '%Y-%m-%d').date() if ab else None
    takt.gueltig_bis = datetime.strptime(bis, '%Y-%m-%d').date() if bis else None
    if takt.gueltig_ab and takt.gueltig_bis and takt.gueltig_bis < takt.gueltig_ab:
        raise ValueError('„gültig bis“ liegt vor „gültig ab“')
    takt.notiz = form.get('notiz', '').strip() or None


@content_calendar_bp.route('/content-calendar/takte', methods=['GET', 'POST'])
def content_takte():
    if request.method == 'POST':
        takt_id = request.form.get('takt_id', type=int)
        takt = ContentTakt.query.get_or_404(takt_id) if takt_id else ContentTakt()
        try:
            _takt_aus_form(takt, request.form)
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(f'Takt nicht gespeichert: {exc}', 'error')
            return redirect(url_for('content_calendar_bp.content_takte', edit=takt_id or None))
        if not takt_id:
            db.session.add(takt)
        db.session.commit()
        flash('Takt gespeichert', 'success')
        return redirect(url_for('content_calendar_bp.content_takte'))

    today = date.today()
    wochen = request.args.get('wochen', type=int) or content_takt.HORIZONT_WOCHEN
    wochen = max(1, min(wochen, 26))
    takte, eintraege, ohne_takt = content_takt.lade(db.session.connection().connection, today)
    abdeckung = content_takt.abdeckung(takte, eintraege, today, wochen)
    edit_id = request.args.get('edit', type=int)
    return render_template(
        'content_takte.html', abdeckung=abdeckung, ohne_takt=ohne_takt,
        luecken=content_takt.luecken(abdeckung), wochen=wochen, today=today,
        edit=ContentTakt.query.get(edit_id) if edit_id else None,
        contacts=_customer_contacts(), platforms=CONTENT_PLATFORMS,
        einheiten=CONTENT_TAKT_EINHEITEN)


@content_calendar_bp.route('/content-calendar/takte/<int:id>/delete', methods=['POST'])
def content_takt_delete(id):
    takt = ContentTakt.query.get_or_404(id)
    db.session.delete(takt)
    db.session.commit()
    flash('Takt gelöscht', 'success')
    return redirect(url_for('content_calendar_bp.content_takte'))



@content_calendar_bp.route('/content-calendar/new', methods=['GET', 'POST'])
def content_calendar_new():
    if request.method == 'POST':
        entry = ContentCalendarEntry(
            contact_id=request.form.get('contact_id', type=int) or None,
            platform=request.form.get('platform') or CONTENT_PLATFORMS[0][0],
            status=request.form.get('status') or 'rohentwurf',
            title=request.form.get('title', '').strip(),
            content_text=request.form.get('content_text', '').strip() or None,
            asset_link=request.form.get('asset_link', '').strip() or None,
            scheduled_for=_parse_datetime_local(request.form.get('scheduled_for')),
            category=request.form.get('category', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None,
        )

        if not entry.title:
            flash('Titel ist erforderlich', 'error')
            return render_template('content_calendar_form.html', entry=None,
                                   contacts=_customer_contacts(),
                                   stages=CONTENT_CALENDAR_STAGES, platforms=CONTENT_PLATFORMS)

        db.session.add(entry)
        db.session.commit()
        flash('Content-Eintrag erstellt', 'success')
        return redirect(url_for('content_calendar_bp.content_calendar'))

    preselect_status = request.args.get('status', 'rohentwurf')
    preselect_contact = request.args.get('contact_id', type=int)
    return render_template('content_calendar_form.html', entry=None,
                           contacts=_customer_contacts(),
                           stages=CONTENT_CALENDAR_STAGES, platforms=CONTENT_PLATFORMS,
                           preselect_status=preselect_status, preselect_contact=preselect_contact)


@content_calendar_bp.route('/content-calendar/<int:id>', methods=['GET', 'POST'])
def content_calendar_view(id):
    entry = ContentCalendarEntry.query.get_or_404(id)

    if request.method == 'POST':
        error = _outbox_withdraw(entry)
        if error:
            flash(error, 'error')
            return redirect(url_for('content_calendar_bp.content_calendar_view', id=id))
        if 'contact_id' in request.form:
            entry.contact_id = request.form.get('contact_id', type=int) or None
        entry.platform = request.form.get('platform') or entry.platform
        old_status = entry.status
        entry.status = request.form.get('status') or entry.status
        entry.title = request.form.get('title', '').strip()
        entry.content_text = request.form.get('content_text', '').strip() or None
        entry.asset_link = request.form.get('asset_link', '').strip() or None
        entry.scheduled_for = _parse_datetime_local(request.form.get('scheduled_for'))
        entry.category = request.form.get('category', '').strip() or None
        entry.notes = request.form.get('notes', '').strip() or None

        if entry.status == 'posted' and old_status != 'posted':
            entry.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        elif entry.status != 'posted':
            entry.posted_at = None

        db.session.commit()
        if entry.status == 'scheduled':
            _outbox_im_hintergrund()
        flash('Content-Eintrag aktualisiert', 'success')
        return redirect(url_for('content_calendar_bp.content_calendar'))

    return render_template('content_calendar_form.html', entry=entry,
                           contacts=_form_contacts(entry.contact),
                           stages=CONTENT_CALENDAR_STAGES, platforms=CONTENT_PLATFORMS,
                           preview=_feed_preview(entry))



FEED_FOLD = {'linkedin': 210, 'linkedin_page': 210, 'instagram': 125, 'facebook': 480}
IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
               '.gif': 'image/gif', '.webp': 'image/webp', '.mp4': 'video/mp4', '.mov': 'video/quicktime'}


def _feed_preview(entry):
    from content_publisher import asset_paths, first_comment, check_entry, PUBLISH_PLATFORMS
    link = (entry.asset_link or '').strip()
    if link.startswith(('http://', 'https://')):
        media = [dict(n=0, name=link, exists=True, video=False, url=link)]
    else:
        media = [dict(n=i, name=p.name, exists=p.is_file(),
                      video=p.suffix.lower() in ('.mp4', '.mov'))
                 for i, p in enumerate(asset_paths(link) if link else [])]
    text = (entry.content_text or '').strip()
    fold = FEED_FOLD.get(entry.platform)
    return dict(
        text=text,
        above_fold=text[:fold] if fold and len(text) > fold else text,
        folded=bool(fold and len(text) > fold),
        media=media,
        publisher_kanal=entry.platform in PUBLISH_PLATFORMS,
        comment=first_comment(entry),
        problem=check_entry(entry) if entry.platform in PUBLISH_PLATFORMS else None,
        author=entry.contact.organisation if entry.contact and entry.contact_id != 315
        else ('Musterwerkstatt' if entry.platform == 'linkedin_page' else 'Max Mustermann'),
    )


@content_calendar_bp.route('/content-calendar/<int:id>/asset/<int:n>')
def content_calendar_asset(id, n):
    import io
    from flask import send_file, abort
    from content_publisher import asset_paths
    entry = ContentCalendarEntry.query.get_or_404(id)
    paths = asset_paths(entry.asset_link) if entry.asset_link else []
    if n >= len(paths) or not paths[n].is_file() or paths[n].suffix.lower() not in IMAGE_TYPES:
        abort(404)
    return send_file(io.BytesIO(paths[n].read_bytes()), mimetype=IMAGE_TYPES[paths[n].suffix.lower()])


@content_calendar_bp.route('/content-calendar/<int:id>/move', methods=['POST'])
def content_calendar_move(id):
    entry = ContentCalendarEntry.query.get_or_404(id)
    data = request.get_json() or {}
    new_status = data.get('status')

    valid_statuses = [s[0] for s in CONTENT_CALENDAR_STAGES]
    if not new_status or new_status not in valid_statuses:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    if new_status == 'scheduled' and entry.status != 'scheduled':
        return jsonify({'success': False, 'error': 'Freigabe nur in der Vorschau',
                        'href': url_for('content_calendar_bp.content_calendar_view', id=id)}), 409

    if new_status != entry.status:
        error = _outbox_withdraw(entry)
        if error:
            flash(error, 'error')
            return jsonify({'success': False, 'error': error,
                            'href': url_for('content_calendar_bp.content_calendar_view', id=id)}), 409

    old_status = entry.status
    try:
        entry.status = new_status
        if new_status == 'posted' and old_status != 'posted':
            entry.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        elif new_status != 'posted':
            entry.posted_at = None
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500

    return jsonify({'success': True})


@content_calendar_bp.route('/content-calendar/publish-due', methods=['POST'])
def content_calendar_publish_due():
    from content_publisher import run_due

    confirm = request.form.get('confirm') == '1'
    try:
        results = run_due(dry_run=not confirm)
    except Exception as exc:
        db.session.rollback()
        flash(f'Publishing-Lauf abgebrochen: {type(exc).__name__}: {exc}', 'error')
        return redirect(url_for('content_calendar_bp.content_calendar'))

    if not results:
        flash('Nichts faellig: kein Eintrag auf "Scheduled" mit erreichtem Termin.', 'info')
        return redirect(url_for('content_calendar_bp.content_calendar'))

    ok = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    if confirm:
        if ok:
            flash(f'{len(ok)} Eintrag/Eintraege veroeffentlicht und auf "Posted" gesetzt.', 'success')
    else:
        flash(f'Probelauf: {len(ok)} von {len(results)} waeren postbar. '
              f'Nichts veroeffentlicht, nichts am Status geaendert.', 'info')
    for entry, _ok, message in failed:
        flash(f'#{entry.id} "{entry.title[:40]}": {message}', 'error')
    return redirect(url_for('content_calendar_bp.content_calendar'))


@content_calendar_bp.route('/content-calendar/<int:id>/delete', methods=['POST'])
def content_calendar_delete(id):
    entry = ContentCalendarEntry.query.get_or_404(id)
    error = _outbox_withdraw(entry)
    if error:
        flash(error, 'error')
        return redirect(url_for('content_calendar_bp.content_calendar_view', id=id))
    db.session.delete(entry)
    db.session.commit()
    flash('Content-Eintrag gelöscht', 'success')
    return redirect(url_for('content_calendar_bp.content_calendar'))

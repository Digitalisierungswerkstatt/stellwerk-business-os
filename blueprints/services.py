import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import func

from models import (
    db, ServiceTemplate, GroupTemplate, GroupTemplateItem,
    ConditionsTemplate, Document,
    SERVICE_CATEGORIES, UNIT_OPTIONS, BILLING_TYPES,
)

services_bp = Blueprint('services_bp', __name__, url_prefix='')



@services_bp.app_template_filter('tojson_service')
def tojson_service_filter(svc):
    return json.dumps({
        'id': svc.id,
        'category': svc.category,
        'title': svc.title,
        'description': svc.description or '',
        'unit_price': float(svc.unit_price),
        'unit': svc.unit,
        'billing_type': svc.billing_type,
        'active': svc.active,
    })


@services_bp.app_template_filter('tojson_group_template')
def tojson_group_template_filter(gt):
    return json.dumps({
        'id': gt.id,
        'title': gt.title,
        'description': gt.description or '',
        'active': gt.active,
        'items': [{
            'title': item.title,
            'description': item.description or '',
            'quantity': float(item.quantity),
            'unit': item.unit,
            'unit_price': float(item.unit_price),
            'billing_type': item.billing_type,
            'service_template_id': item.service_template_id,
        } for item in gt.items],
    })



@services_bp.route('/services')
def services():
    all_services = ServiceTemplate.query.order_by(ServiceTemplate.category, ServiceTemplate.position).all()
    grouped = {}
    for svc in all_services:
        grouped.setdefault(svc.category, []).append(svc)
    group_templates = GroupTemplate.query.order_by(GroupTemplate.position).all()
    conditions_templates = ConditionsTemplate.query.order_by(ConditionsTemplate.position).all()
    return render_template('services.html', grouped=grouped,
                           categories=SERVICE_CATEGORIES,
                           unit_options=UNIT_OPTIONS,
                           billing_types=BILLING_TYPES,
                           group_templates=group_templates,
                           conditions_templates=conditions_templates)


@services_bp.route('/services/new', methods=['POST'])
def service_create():
    data = request.get_json()
    max_pos = db.session.query(func.max(ServiceTemplate.position)).filter_by(
        category=data.get('category', '')).scalar() or 0
    svc = ServiceTemplate(
        category=data.get('category', ''),
        title=data.get('title', ''),
        description=data.get('description', ''),
        unit_price=data.get('unit_price', 0),
        unit=data.get('unit', 'Einmalig'),
        billing_type=data.get('billing_type', 'onetime'),
        position=max_pos + 1,
        active=True,
    )
    db.session.add(svc)
    db.session.commit()
    return jsonify({'success': True, 'id': svc.id})


@services_bp.route('/services/<int:id>/edit', methods=['POST'])
def service_edit(id):
    svc = ServiceTemplate.query.get_or_404(id)
    data = request.get_json()
    svc.category = data.get('category', svc.category)
    svc.title = data.get('title', svc.title)
    svc.description = data.get('description', svc.description)
    svc.unit_price = data.get('unit_price', svc.unit_price)
    svc.unit = data.get('unit', svc.unit)
    svc.billing_type = data.get('billing_type', svc.billing_type)
    svc.active = data.get('active', svc.active)
    db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/services/<int:id>/delete', methods=['POST'])
def service_delete(id):
    svc = ServiceTemplate.query.get_or_404(id)
    db.session.delete(svc)
    db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/api/services')
def api_services():
    services = ServiceTemplate.query.filter_by(active=True).order_by(
        ServiceTemplate.category, ServiceTemplate.position).all()
    cat_dict = dict(SERVICE_CATEGORIES)
    return jsonify([{
        'id': s.id,
        'category': s.category,
        'category_label': cat_dict.get(s.category, s.category),
        'title': s.title,
        'description': s.description or '',
        'unit_price': float(s.unit_price),
        'unit': s.unit,
        'billing_type': s.billing_type,
        'use_count': s.use_count,
    } for s in services])


@services_bp.route('/api/services/bump-usage', methods=['POST'])
def api_services_bump_usage():
    data = request.get_json()
    titles = data.get('titles', [])
    if titles:
        for svc in ServiceTemplate.query.filter(ServiceTemplate.title.in_(titles)).all():
            svc.use_count = (svc.use_count or 0) + 1
        db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/api/documents/<int:id>/groups')
def api_document_groups(id):
    doc = Document.query.get_or_404(id)
    return jsonify({
        'id': doc.id,
        'number': doc.number,
        'subject': doc.subject,
        'groups': [{
            'title': g.title,
            'description': g.description or '',
            'items': [{
                'title': item.title,
                'description': item.description or '',
                'quantity': float(item.quantity),
                'unit': item.unit,
                'unit_price': float(item.unit_price),
                'billing_type': item.billing_type,
            } for item in g.items],
        } for g in doc.groups],
    })


@services_bp.route('/api/documents/search')
def api_documents_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    docs = Document.query.filter(
        db.or_(
            Document.number.ilike(f'%{q}%'),
            Document.subject.ilike(f'%{q}%'),
        )
    ).order_by(Document.date.desc()).limit(10).all()
    return jsonify([{
        'id': d.id,
        'number': d.number,
        'subject': d.subject,
        'type_label': d.type_label,
        'contact': d.contact.display_name,
        'group_count': len(d.groups),
    } for d in docs])



@services_bp.route('/group-templates/new', methods=['POST'])
def group_template_create():
    data = request.get_json()
    max_pos = db.session.query(func.max(GroupTemplate.position)).scalar() or 0
    gt = GroupTemplate(
        title=data.get('title', ''),
        description=data.get('description', ''),
        position=max_pos + 1,
        active=True,
    )
    db.session.add(gt)
    db.session.flush()

    for i_idx, item_data in enumerate(data.get('items', [])):
        item = GroupTemplateItem(
            group_template_id=gt.id,
            service_template_id=item_data.get('service_template_id') or None,
            title=item_data.get('title', ''),
            description=item_data.get('description', ''),
            quantity=item_data.get('quantity', 1),
            unit=item_data.get('unit', 'Einmalig'),
            unit_price=item_data.get('unit_price', 0),
            billing_type=item_data.get('billing_type', 'onetime'),
            position=i_idx,
        )
        db.session.add(item)

    db.session.commit()
    return jsonify({'success': True, 'id': gt.id})


@services_bp.route('/group-templates/<int:id>/edit', methods=['POST'])
def group_template_edit(id):
    gt = GroupTemplate.query.get_or_404(id)
    data = request.get_json()
    gt.title = data.get('title', gt.title)
    gt.description = data.get('description', gt.description)
    gt.active = data.get('active', gt.active)

    GroupTemplateItem.query.filter_by(group_template_id=gt.id).delete()
    for i_idx, item_data in enumerate(data.get('items', [])):
        item = GroupTemplateItem(
            group_template_id=gt.id,
            service_template_id=item_data.get('service_template_id') or None,
            title=item_data.get('title', ''),
            description=item_data.get('description', ''),
            quantity=item_data.get('quantity', 1),
            unit=item_data.get('unit', 'Einmalig'),
            unit_price=item_data.get('unit_price', 0),
            billing_type=item_data.get('billing_type', 'onetime'),
            position=i_idx,
        )
        db.session.add(item)

    db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/group-templates/<int:id>/delete', methods=['POST'])
def group_template_delete(id):
    gt = GroupTemplate.query.get_or_404(id)
    db.session.delete(gt)
    db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/api/group-templates')
def api_group_templates():
    templates = GroupTemplate.query.filter_by(active=True).order_by(GroupTemplate.position).all()
    return jsonify([{
        'id': gt.id,
        'title': gt.title,
        'description': gt.description or '',
        'items': [{
            'title': item.title,
            'description': item.description or '',
            'quantity': float(item.quantity),
            'unit': item.unit,
            'unit_price': float(item.unit_price),
            'billing_type': item.billing_type,
        } for item in gt.items],
    } for gt in templates])


@services_bp.route('/documents/<int:doc_id>/groups/<int:group_idx>/save-as-template', methods=['POST'])
def save_group_as_template(doc_id, group_idx):
    doc = Document.query.get_or_404(doc_id)
    if group_idx < 0 or group_idx >= len(doc.groups):
        return jsonify({'error': 'Gruppe nicht gefunden'}), 404
    group = doc.groups[group_idx]

    max_pos = db.session.query(func.max(GroupTemplate.position)).scalar() or 0
    gt = GroupTemplate(
        title=group.title or f'Vorlage aus {doc.number}',
        description=group.description or '',
        position=max_pos + 1,
        active=True,
    )
    db.session.add(gt)
    db.session.flush()

    for i_idx, item in enumerate(group.items):
        gti = GroupTemplateItem(
            group_template_id=gt.id,
            title=item.title,
            description=item.description or '',
            quantity=float(item.quantity),
            unit=item.unit,
            unit_price=float(item.unit_price),
            billing_type=item.billing_type,
            position=i_idx,
        )
        db.session.add(gti)

    db.session.commit()
    flash(f'Gruppen-Vorlage "{gt.title}" gespeichert.', 'success')
    return jsonify({'success': True, 'id': gt.id, 'title': gt.title})



@services_bp.route('/api/conditions-templates')
def api_conditions_templates():
    templates = ConditionsTemplate.query.filter_by(active=True).order_by(ConditionsTemplate.position).all()
    return jsonify([{'id': t.id, 'name': t.name, 'text': t.text, 'payment_term_days': t.payment_term_days} for t in templates])


@services_bp.route('/conditions-templates/new', methods=['POST'])
def conditions_template_create():
    data = request.get_json()
    max_pos = db.session.query(func.max(ConditionsTemplate.position)).scalar() or 0
    t = ConditionsTemplate(name=data.get('name', ''), text=data.get('text', ''), payment_term_days=data.get('payment_term_days', 14), position=max_pos + 1, active=True)
    db.session.add(t)
    db.session.commit()
    return jsonify({'success': True, 'id': t.id})


@services_bp.route('/conditions-templates/<int:id>/edit', methods=['POST'])
def conditions_template_edit(id):
    t = ConditionsTemplate.query.get_or_404(id)
    data = request.get_json()
    t.name = data.get('name', t.name)
    t.text = data.get('text', t.text)
    t.active = data.get('active', t.active)
    db.session.commit()
    return jsonify({'success': True})


@services_bp.route('/conditions-templates/<int:id>/delete', methods=['POST'])
def conditions_template_delete(id):
    t = ConditionsTemplate.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True})

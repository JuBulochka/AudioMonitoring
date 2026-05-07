"""
Operator management views — admin-only.

Flow for creating an operator:
  1. Admin fills: last_name, first_name, middle_name (opt), email (opt), phone (opt)
  2. System auto-generates: employee_number, username, password
  3. Credentials stored in session, redirected to credentials page
  4. Credentials page pops session → shown ONCE with copy buttons
  5. Password never retrievable again (only hash stored)
"""
import re
import secrets
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.devices.models import Field
from .access import admin_required
from .models import OperatorProfile, User, UserRole

# ── Transliteration (Russian → Latin for username generation) ─────────────────
_TRANSLIT = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'g',  'д': 'd',
    'е': 'e',  'ё': 'e',  'ж': 'zh', 'з': 'z',  'и': 'i',
    'й': 'y',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
    'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',
    'у': 'u',  'ф': 'f',  'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sch','ъ': '',   'ы': 'y',  'ь': '',
    'э': 'e',  'ю': 'yu', 'я': 'ya',
}

def _translit(text: str) -> str:
    return ''.join(_TRANSLIT.get(ch, ch) for ch in text.lower())


def _generate_employee_number() -> str:
    count = User.objects.filter(role=UserRole.OPERATOR).count() + 1
    candidate = f'OP-{count:04d}'
    while User.objects.filter(employee_number=candidate).exists():
        count += 1
        candidate = f'OP-{count:04d}'
    return candidate


def _generate_username(last_name: str, first_name: str) -> str:
    last  = re.sub(r'[^a-z0-9]', '', _translit(last_name))
    first = re.sub(r'[^a-z0-9]', '', _translit(first_name))
    base  = f'{last}.{first[0]}' if first else last
    base  = base[:20] or 'operator'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{n}'
        n += 1
    return username


def _generate_password(length: int = 14) -> str:
    chars = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(chars) for _ in range(length))


# ── Views ──────────────────────────────────────────────────────────────────────

@admin_required
def operator_list(request):
    qs = (
        User.objects
        .filter(role=UserRole.OPERATOR)
        .prefetch_related('profile__assigned_fields')
        .order_by('last_name', 'first_name')
    )
    search = request.GET.get('q', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(username__icontains=search) |
            Q(employee_number__icontains=search)
        )

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'users/operator_list.html', {
        'operators': page,
        'paginator': paginator,
        'filter_q': search,
    })


@admin_required
def operator_create(request):
    all_fields = Field.objects.select_related('region').order_by('region__name', 'name')

    if request.method == 'POST':
        last_name   = request.POST.get('last_name',   '').strip()
        first_name  = request.POST.get('first_name',  '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        email       = request.POST.get('email',       '').strip()
        phone       = request.POST.get('phone',       '').strip()
        field_ids   = request.POST.getlist('field_ids')

        if not last_name or not first_name:
            messages.error(request, 'Фамилия и имя обязательны.')
            return render(request, 'users/operator_create.html', {
                'all_fields': all_fields, 'post': request.POST
            })

        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Пользователь с таким email уже существует.')
            return render(request, 'users/operator_create.html', {
                'all_fields': all_fields, 'post': request.POST
            })

        with transaction.atomic():
            employee_number = _generate_employee_number()
            username        = _generate_username(last_name, first_name)
            password        = _generate_password()

            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                role=UserRole.OPERATOR,
                employee_number=employee_number,
            )
            # Store middle name in a comment / notes — use last_name field trick
            # Actually store full_name parts properly via first/last; middle via profile
            profile, _ = OperatorProfile.objects.get_or_create(user=user)
            if field_ids:
                profile.assigned_fields.set(Field.objects.filter(id__in=field_ids))

        # Store credentials in session (shown ONCE on next page)
        request.session['new_operator_creds'] = {
            'user_id':         user.pk,
            'employee_number': employee_number,
            'username':        username,
            'password':        password,
            'full_name':       f'{last_name} {first_name}' + (f' {middle_name}' if middle_name else ''),
        }
        return redirect('operator-credentials', pk=user.pk)

    return render(request, 'users/operator_create.html', {
        'all_fields': all_fields,
        'post': {},
    })


@admin_required
def operator_credentials(request, pk):
    """Show auto-generated credentials ONCE, then clear from session."""
    operator = get_object_or_404(User, pk=pk, role=UserRole.OPERATOR)
    creds = request.session.pop('new_operator_creds', None)
    if not creds or creds.get('user_id') != pk:
        messages.warning(request, 'Учётные данные уже были показаны или недоступны.')
        return redirect('operator-detail', pk=pk)
    return render(request, 'users/operator_credentials.html', {
        'operator': operator,
        'creds': creds,
    })


@admin_required
def operator_detail(request, pk):
    operator = get_object_or_404(User, pk=pk, role=UserRole.OPERATOR)
    profile, _ = OperatorProfile.objects.get_or_create(user=operator)
    all_fields = Field.objects.select_related('region').order_by('region__name', 'name')
    assigned_ids = set(profile.assigned_fields.values_list('id', flat=True))

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'save':
            operator.first_name = request.POST.get('first_name', operator.first_name).strip()
            operator.last_name  = request.POST.get('last_name',  operator.last_name).strip()
            operator.email      = request.POST.get('email',  operator.email).strip()
            operator.phone      = request.POST.get('phone',  operator.phone).strip()
            operator.save(update_fields=['first_name', 'last_name', 'email', 'phone'])

            field_ids = request.POST.getlist('field_ids')
            profile.assigned_fields.set(Field.objects.filter(id__in=field_ids))
            messages.success(request, 'Данные оператора сохранены.')

        elif action == 'toggle_freeze':
            operator.is_frozen = not operator.is_frozen
            operator.save(update_fields=['is_frozen'])
            status = 'заморожен' if operator.is_frozen else 'разморожен'
            messages.success(request, f'Аккаунт {operator.full_name} {status}.')

        elif action == 'reset_password':
            new_password = _generate_password()
            operator.set_password(new_password)
            operator.save(update_fields=['password'])
            # Store in session for one-time display
            request.session['new_operator_creds'] = {
                'user_id':         pk,
                'employee_number': operator.employee_number,
                'username':        operator.username,
                'password':        new_password,
                'full_name':       operator.full_name,
                'is_reset':        True,
            }
            return redirect('operator-credentials', pk=pk)

        return redirect('operator-detail', pk=pk)

    return render(request, 'users/operator_detail.html', {
        'operator':      operator,
        'profile':       profile,
        'all_fields':    all_fields,
        'assigned_ids':  assigned_ids,
    })

/* ===== OLDEV Lead Magnet — Email Deliverability Audit Form ===== */

// >>> CONFIG: Paste your n8n webhook URL here once the flow is built <<<
const N8N_WEBHOOK_URL = 'REPLACE_WITH_N8N_WEBHOOK_URL';

// Domain validation: accepts foo.com, sub.foo.co.uk, etc. (no protocol, no path).
const DOMAIN_RE = /^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function normalizeDomain(value) {
    return value
        .trim()
        .toLowerCase()
        .replace(/^https?:\/\//, '')
        .replace(/^www\./, '')
        .replace(/\/.*$/, '');
}

function setFieldError(form, fieldName, message) {
    const input = form.querySelector(`[name="${fieldName}"]`);
    const errorEl = form.querySelector(`[data-error-for="${fieldName}"]`);
    if (input) input.setAttribute('aria-invalid', message ? 'true' : 'false');
    if (errorEl) errorEl.textContent = message || '';
}

function setFormError(form, message) {
    const formError = form.querySelector('.lm-form-error');
    if (!formError) return;
    if (message) {
        formError.textContent = message;
        formError.removeAttribute('hidden');
    } else {
        formError.textContent = '';
        formError.setAttribute('hidden', '');
    }
}

function validate(form) {
    let valid = true;
    const email = form.elements['email'].value.trim();
    const domainRaw = form.elements['domain'].value;

    setFieldError(form, 'email', '');
    setFieldError(form, 'domain', '');

    if (!email) {
        setFieldError(form, 'email', 'Email is required.');
        valid = false;
    } else if (!EMAIL_RE.test(email)) {
        setFieldError(form, 'email', 'Please enter a valid email address.');
        valid = false;
    }

    const domain = normalizeDomain(domainRaw);
    if (!domain) {
        setFieldError(form, 'domain', 'Domain is required.');
        valid = false;
    } else if (!DOMAIN_RE.test(domain)) {
        setFieldError(form, 'domain', 'Enter a domain like example.com (no http://, no path).');
        valid = false;
    }

    return { valid, email, domain };
}

async function submitLeadMagnet(form, source) {
    setFormError(form, '');

    // Honeypot check — if a bot filled the hidden field, silently abort.
    const honeypot = form.elements['company_website'];
    if (honeypot && honeypot.value.trim() !== '') {
        return { aborted: true };
    }

    const result = validate(form);
    if (!result.valid) return { aborted: true };

    const name = (form.elements['name']?.value || '').trim();
    const payload = {
        email: result.email,
        domain: result.domain,
        name: name || undefined,
        source,
        timestamp: new Date().toISOString(),
    };

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalLabel = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';

    try {
        const response = await fetch(N8N_WEBHOOK_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }
        showSuccess(form);
        return { ok: true };
    } catch (err) {
        const isPlaceholder = N8N_WEBHOOK_URL === 'REPLACE_WITH_N8N_WEBHOOK_URL';
        const message = isPlaceholder
            ? 'Webhook URL not configured yet. Please contact the site owner directly.'
            : 'Could not reach the audit service. Please try again or contact us directly.';
        setFormError(form, message);
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
        return { ok: false, error: err };
    }
}

function showSuccess(form) {
    const wrapper = form.closest('.lead-magnet') || form.parentElement;
    const successEl = wrapper.querySelector('.lead-magnet-success');
    form.setAttribute('hidden', '');
    if (successEl) successEl.removeAttribute('hidden');
}

function initLeadMagnet(form) {
    if (!form || form.dataset.lmInit === '1') return;
    form.dataset.lmInit = '1';
    const source = form.dataset.source || 'unknown';

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitLeadMagnet(form, source);
    });

    // Live-clear errors as user edits
    ['email', 'domain'].forEach((fieldName) => {
        const input = form.elements[fieldName];
        if (!input) return;
        input.addEventListener('input', () => setFieldError(form, fieldName, ''));
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.lead-magnet-form').forEach(initLeadMagnet);
});

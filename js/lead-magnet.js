/* ===== OLDEV Lead Magnet — Email Deliverability Audit Form ===== */

const N8N_WEBHOOK_URL = 'https://n8n.oldev.site/webhook/audit-request';
const REQUEST_TIMEOUT_MS = 10_000;

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

function classifyError(err, response) {
    if (err && err.name === 'AbortError') {
        return 'Request took too long. Please try again.';
    }
    if (response) {
        if (response.status >= 500) {
            return "Something's broken on our end — try again in a minute.";
        }
        if (response.status >= 400) {
            return 'Please check your email and domain are valid.';
        }
    }
    return "Couldn't reach our server. Check your connection and try again.";
}

async function submitLeadMagnet(form, source) {
    setFormError(form, '');

    // Honeypot — defense-in-depth (n8n also rejects). Silently abort.
    const honeypotField = form.elements['company_website'];
    const honeypotValue = honeypotField ? honeypotField.value.trim() : '';
    if (honeypotValue !== '') {
        return { aborted: true, reason: 'honeypot' };
    }

    const result = validate(form);
    if (!result.valid) return { aborted: true, reason: 'validation' };

    const name = (form.elements['name']?.value || '').trim();
    const payload = {
        email: result.email,
        domain: result.domain,
        name: name || undefined,
        source,
        timestamp: new Date().toISOString(),
        honeypot: honeypotValue,
    };

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalLabel = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let response = null;
    try {
        response = await fetch(N8N_WEBHOOK_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            const message = classifyError(null, response);
            setFormError(form, message);
            submitBtn.disabled = false;
            submitBtn.textContent = originalLabel;
            return { ok: false, status: response.status };
        }

        showSuccess(form);
        return { ok: true };
    } catch (err) {
        clearTimeout(timeoutId);
        const message = classifyError(err, null);
        setFormError(form, message);
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
        return { ok: false, error: err.name || 'NetworkError' };
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

    ['email', 'domain'].forEach((fieldName) => {
        const input = form.elements[fieldName];
        if (!input) return;
        input.addEventListener('input', () => setFieldError(form, fieldName, ''));
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.lead-magnet-form').forEach(initLeadMagnet);
});

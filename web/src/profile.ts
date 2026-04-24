import './style.css';
import $ from 'jquery';
import { getToken, getMe, updateProfile } from './api';

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        const user = await getMe();
        // Pre-fill existing profile data
        if (user.name) $('#name').val(user.name);
        if (user.affiliation) $('#affiliation').val(user.affiliation);
        if (user.email) $('#email').val(user.email);
        if (user.credit_consent) $('#credit-consent').prop('checked', true);
    } catch {
        window.location.href = '/';
        return;
    }

    $('#save-btn').on('click', async () => {
        const name = String($('#name').val()).trim();
        const affiliation = String($('#affiliation').val()).trim();
        const email = String($('#email').val()).trim();
        const credit_consent = Boolean($('#credit-consent').prop('checked'));
        const terms = Boolean($('#terms').prop('checked'));

        if (!name || !email) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text('Name and email are required.');
            return;
        }
        if (!terms) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text('You must accept the terms of use to continue.');
            return;
        }

        $('#save-btn').prop('disabled', true);
        try {
            await updateProfile({ name, affiliation, email, credit_consent });

            // Redirect back to main page which will route appropriately
            window.location.href = '/' + window.location.search;
        } catch (err) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text(String(err));
            $('#save-btn').prop('disabled', false);
        }
    });
});

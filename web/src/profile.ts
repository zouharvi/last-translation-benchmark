import './style.css';
import $ from 'jquery';

import { getToken, getUsername, getMe, updateProfile, register } from './api';
import { setupInstructions } from './utils';

$(async () => {
    setupInstructions('all');
    const hasAuth = Boolean(getToken() && getUsername());

    if (hasAuth) {
        try {
            const user = await getMe();
            // Pre-fill existing profile data
            if (user.name) $('#name').val(user.name);
            if (user.affiliation) $('#affiliation').val(user.affiliation);
            if (user.email) $('#email').val(user.email);
            if (user.credit_consent) $('#credit-consent').prop('checked', true);
        } catch {
            window.location.href = 'index.html';
            return;
        }
    } else {
        $('#profile-heading').text('Request Access');
        $('#profile-sub').text('Fill in your details and wait for a confirmation email with your login link.');
        $('#save-btn').text('Submit Registration');
    }

    $('#save-btn').on('click', async () => {
        const name = String($('#name').val()).trim();
        const affiliation = String($('#affiliation').val()).trim();
        const email = String($('#email').val()).trim();
        const credit_consent = Boolean($('#credit-consent').prop('checked'));

        if (!name || !email) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text('Name and email are required.');
            return;
        }

        $('#save-btn').prop('disabled', true);
        try {
            if (hasAuth) {
                await updateProfile({ name, affiliation, email, credit_consent });
                window.location.href = 'index.html' + window.location.search;
            } else {
                await register({ name, affiliation, email, credit_consent });
                $('#status-msg').removeClass('msg-err').addClass('msg-ok').text(
                    'Registration received! You will receive a login link via email once your account is confirmed.'
                );
            }
        } catch (err) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text(String(err));
            $('#save-btn').prop('disabled', false);
        }
    });
});

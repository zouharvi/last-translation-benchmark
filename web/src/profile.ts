import './assets/style.css';
import $ from 'jquery';

import { getCookie, getMe, updateProfile, registerUser, recoverLink, renderRoleSwitcher } from './api';
import { renderHeaderStatus } from './utils';

$(async () => {

    const isRegistrationMode = !getCookie('ltb_token');

    if (!isRegistrationMode) {
        try {
            const user = await getMe();
            // Pre-fill existing profile data
            if (user.name) $('#name').val(user.name);
            if (user.affiliation) $('#affiliation').val(user.affiliation);
            if (user.email) $('#email').val(user.email);
            if (user.credit_consent) $('#credit-consent').prop('checked', true);
            if (user.notification_consent === false) $('#notification-consent').prop('checked', false);

            // Populate header status
            renderHeaderStatus(user);
            renderRoleSwitcher(user.roles);
        } catch {
            window.location.href = 'index.html';
            return;
        }
    } else {
        // Change text for registration mode
        $('.profile-wrap h2').text('Register as Contributor');
        $('#registration-form .sub').text('Fill out your details to request an account (can be modified later).');
        $('#recover-link-container').show();
    }

    $('#save-btn').on('click', async () => {
        const name = String($('#name').val()).trim();
        const affiliation = String($('#affiliation').val()).trim();
        const email = String($('#email').val()).trim();
        const credit_consent = Boolean($('#credit-consent').prop('checked'));
        const notification_consent = Boolean($('#notification-consent').prop('checked'));

        if (!name || !email) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text('Name and email are required.');
            return;
        }

        $('#save-btn').prop('disabled', true);
        try {
            if (isRegistrationMode) {
                await registerUser({ name, affiliation, email, credit_consent, notification_consent });
                window.location.href = 'index.html?registered=1';
            } else {
                await updateProfile({ name, affiliation, email, credit_consent, notification_consent });
                // Redirect back to main page which will route appropriately
                window.location.href = 'index.html';
            }
        } catch (err) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text(String(err));
            $('#save-btn').prop('disabled', false);
        }
    });

    $('#show-recover-btn').on('click', (e) => {
        e.preventDefault();
        $('#registration-form').hide();
        $('#recover-window').show();
        $('#recover-form-content').show();
        $('.profile-wrap h2').text('Recover Login Link');
        $('#recover-status-msg').text('').removeClass('msg-ok msg-err').css('color', '');
        $('#recover-email').prop('disabled', false).val('');
        $('#send-recover-btn').prop('disabled', false);
    });

    $('#back-to-register-btn').on('click', (e) => {
        e.preventDefault();
        $('#recover-window').hide();
        $('#registration-form').show();
        $('.profile-wrap h2').text('Register as Contributor');
    });

    $('#send-recover-btn').on('click', async () => {
        const email = String($('#recover-email').val()).trim();
        if (!email) {
            $('#recover-status-msg').removeClass('msg-ok').addClass('msg-err').text('Please enter your email.');
            return;
        }

        $('#send-recover-btn').prop('disabled', true);
        $('#recover-email').prop('disabled', true);
        try {
            await recoverLink(email);
            $('#recover-form-content').hide();
            $('#recover-status-msg').removeClass('msg-err msg-ok').css('color', 'inherit').text('If an account exists, a link has been sent.');
            $('#recover-email').val('');
            // Do not re-enable on success
        } catch (err) {
            $('#recover-status-msg').removeClass('msg-ok').addClass('msg-err').text('Failed to process request.');
            $('#send-recover-btn').prop('disabled', false);
            $('#recover-email').prop('disabled', false);
        }
    });
});

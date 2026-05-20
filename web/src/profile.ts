import './assets/style.css';
import $ from 'jquery';

import { getCookie, getMe, updateProfile, registerUser } from './api';
import { setupInstructions } from './utils';

$(async () => {
    setupInstructions('all');
    
    const isRegistrationMode = !getCookie('ltb_token');

    if (!isRegistrationMode) {
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
        // Change text for registration mode
        $('.profile-wrap h2').text('Register as Contributor');
        $('.sub').text('Fill out your details to request an account. An administrator will review your request and send you a login link.');
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
            if (isRegistrationMode) {
                await registerUser({ name, affiliation, email, credit_consent });
                
                // Show success message and hide form
                $('.profile-wrap').html(`
                    <h2>Registration Successful</h2>
                    <p class="sub" style="margin-bottom: 0;">Your profile has been created. Please wait for an administrator to email your login link.</p>
                    <div style="text-align: center; margin-top: 24px;">
                        <a href="index.html" class="btn btn-secondary" style="text-decoration: none; display: inline-block;">Return to Home</a>
                    </div>
                `);
            } else {
                await updateProfile({ name, affiliation, email, credit_consent });
                // Redirect back to main page which will route appropriately
                window.location.href = 'index.html';
            }
        } catch (err) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text(String(err));
            $('#save-btn').prop('disabled', false);
        }
    });
});

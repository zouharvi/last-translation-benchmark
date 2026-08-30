import './assets/style.css';
import $ from 'jquery';
import { getCookie, getMe, renderRoleSwitcher } from './api';
import { renderHeaderStatus } from './utils';

$(async () => {
    if (getCookie('ltb_token')) {
        try {
            const currentUser = await getMe();
            renderHeaderStatus(currentUser);
            renderRoleSwitcher(currentUser.roles);
        } catch {
            // ignore error, just don't show user info
        }
    }

    $('#submission-form').on('submit', async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById('submission-file') as HTMLInputElement;
        if (!fileInput.files || fileInput.files.length === 0) return;
        
        const file = fileInput.files[0];
        const reader = new FileReader();

        reader.onload = async (event) => {
            try {
                const fileContent = event.target?.result as string;
                const jsonData = JSON.parse(fileContent);

                const releaseYear = $('#model-release-year').val();
                const releaseMonth = String($('#model-release-month').val()).padStart(2, '0');

                const payload = {
                    submission: jsonData,
                    model_name: $('#model-name').val(),
                    model_size: $('#model-size').val(),
                    model_release: `${releaseYear}-${releaseMonth}`,
                    model_description: $('#model-description').val(),
                    institution: $('#institution').val(),
                    submitter_email: $('#submitter-email').val(),
                    mode: $('#competition-mode').val()
                };

                const statusEl = $('#submit-status');
                const btn = $('#submit-btn');

                statusEl.text('Submitting...').css('color', 'black');
                btn.prop('disabled', true);

                const response = await fetch('/api/leaderboard', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    let errorMessage = 'Server returned ' + response.status;
                    try {
                        const errorData = await response.json();
                        if (errorData && errorData.detail) {
                            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
                        }
                    } catch (e) {}
                    throw new Error(errorMessage);
                }

                statusEl.text('Submission successful! Waiting on manual confirmation by the administrators.').css('color', 'green');
                ($('#submission-form')[0] as HTMLFormElement).reset();
            } catch (err: any) {
                console.error(err);
                $('#submit-status').text(err.message || 'Error submitting or parsing JSON.').css('color', 'red');
            } finally {
                $('#submit-btn').prop('disabled', false);
            }
        };

        reader.readAsText(file);
    });
});

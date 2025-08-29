document.addEventListener('DOMContentLoaded', () => {
    const questions = document.querySelectorAll('.question');
    if (mode === 'study') {
        questions.forEach(q => {
            const revealBtn = q.querySelector('.reveal');
            if (revealBtn) {
                revealBtn.addEventListener('click', () => {
                    const feedback = q.querySelector('.feedback');
                    feedback.innerHTML = `Correct: ${q.dataset.correct}<br>Explanation: ${q.dataset.explanation}`;
                    feedback.classList.remove('d-none');
                    // Optional coloring (if user answers first - assume radio selected)
                    const selected = q.querySelector('input:checked') ? q.querySelector('input:checked').value : null;
                    if (selected) {
                        feedback.classList.add(selected === q.dataset.correct ? 'correct' : 'incorrect');
                    }
                });
            }
            const flashcard = q.querySelector('.flashcard');
            if (flashcard) {
                flashcard.addEventListener('click', () => flashcard.querySelector('.back').classList.remove('d-none'));
            }
        });
    } else if (mode === 'test') {
        let time = 3600; // 60 min example; adjust as needed
        const timer = document.getElementById('timer');
        const interval = setInterval(() => {
            time--;
            timer.textContent = `Time left: ${Math.floor(time / 60)}:${time % 60 < 10 ? '0' : ''}${time % 60}`;
            if (time <= 0) {
                clearInterval(interval);
                submitTest();
            }
        }, 1000);

        document.getElementById('submit-test').addEventListener('click', submitTest);

        function submitTest() {
            const answers = {};
            let score = 0;
            questions.forEach(q => {
                const id = q.dataset.id;
                const selected = q.querySelector('input:checked') ? q.querySelector('input:checked').value : null;
                answers[id] = selected;
                if (selected === q.dataset.correct) score++;
            });
            score = (score / questions.length * 100).toFixed(2);
            fetch(`/user/quiz/${testId}/${mode}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({score, answers})
            }).then(res => res.json()).then(() => {
                alert(`Submitted! Score: ${score}%`);
                window.location.href = '/user/history';
            });
        }
    }
});
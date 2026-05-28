// 注册页面 JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('register-form');
    
    registerForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        
        // 验证密码
        if (password !== confirmPassword) {
            showError('两次输入的密码不一致');
            return;
        }
        
        // 验证密码长度
        if (password.length < 6) {
            showError('密码长度至少需要6位');
            return;
        }
        
        fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 注册成功，跳转到登录页面
                alert('注册成功！请登录');
                window.location.href = '/login';
            } else {
                showError(data.error || '注册失败');
            }
        })
        .catch(error => {
            console.error('注册失败:', error);
            showError('注册失败，请重试');
        });
    });
    
    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        
        // 移除之前的错误信息
        const existingError = document.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        registerForm.appendChild(errorDiv);
    }
});
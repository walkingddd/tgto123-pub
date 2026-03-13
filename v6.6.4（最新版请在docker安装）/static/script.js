document.addEventListener('DOMContentLoaded', function() {
    const envForm = document.getElementById('env-form');
    const envSections = document.getElementById('env-sections');

    // 从服务器获取.env配置数据
    fetch('/api/env')
        .then(response => response.json())
        .then(data => {
            // 动态生成表单
            const sections = data.sections;
            const order = data.order;

            order.forEach(section => {
                const sectionDiv = document.createElement('div');
                sectionDiv.className = 'section';

                const sectionTitle = document.createElement('h2');
                sectionTitle.textContent = section;
                sectionDiv.appendChild(sectionTitle);

                sections[section].forEach((item, index) => {
                    const configItem = document.createElement('div');
                    configItem.className = 'config-item';

                    const label = document.createElement('label');
                    label.textContent = item.key;
                    label.setAttribute('for', `${section}-${index}`);
                    configItem.appendChild(label);

                    const comment = document.createElement('div');
                    comment.className = 'comment' + (item.comment && item.comment.includes('必填：') ? ' required-comment' : '');
                    comment.textContent = item.comment;
                    configItem.appendChild(comment);

                    const input = document.createElement('input');
                    input.type = 'text';
                    input.id = `${section}-${index}`;
                    input.name = `${section}[${index}]`;
                    input.value = item.value;
                    input.dataset.key = item.key;
                    input.dataset.comment = item.comment;
                    configItem.appendChild(input);

                    sectionDiv.appendChild(configItem);
                });

                envSections.appendChild(sectionDiv);
            });
        })
        .catch(error => {
            console.error('Error fetching env data:', error);
            envSections.innerHTML = '<p class="error">加载配置数据失败</p>';
        });

    // 提交表单
    envForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = {};
        const sections = document.querySelectorAll('.section');

        sections.forEach(section => {
            const sectionTitle = section.querySelector('h2').textContent;
            formData[sectionTitle] = [];

            const inputs = section.querySelectorAll('input');
            inputs.forEach(input => {
                formData[sectionTitle].push({
                    comment: input.dataset.comment,
                    key: input.dataset.key,
                    value: input.value
                });
            });
        });

        // 发送数据到服务器
        fetch('/api/env', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('配置保存成功！');
            } else {
                alert('保存失败，请重试。');
            }
        })
        .catch(error => {
            console.error('Error saving env data:', error);
            alert('正在重启容器');
        });
    });
});
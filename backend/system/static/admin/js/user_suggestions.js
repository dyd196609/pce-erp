(function ($) {
    $(document).ready(function () {
        // 请求后端 API 获取岗位编码建议
        $.ajax({
            url: '/api/system/group-suggestions/',   // 确保 URL 与您配置的一致
            method: 'GET',
            dataType: 'json',
            success: function (data) {
                var suggestions = data.suggestions;
                if (suggestions.length === 0) return;
                // 创建 datalist 元素
                var datalist = $('<datalist id="group_suggestions"></datalist>');
                $.each(suggestions, function (i, val) {
                    datalist.append($('<option>').attr('value', val));
                });
                // 插入到 body 中（或 username 输入框附近）
                $('body').append(datalist);
                // 确保 username 输入框的 list 属性指向它（可能已经设置）
                var usernameInput = $('#id_username');
                if (usernameInput.length && !usernameInput.attr('list')) {
                    usernameInput.attr('list', 'group_suggestions');
                }
            },
            error: function (xhr, status, error) {
                console.log('获取岗位建议失败:', error);
            }
        });
    });
})(django.jQuery);
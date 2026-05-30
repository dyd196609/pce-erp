(function ($) {
    $(document).ready(function () {
        var selectField = $('#id_username_select');
        var manualField = $('#id_username_manual');
        // 如果元素不存在，则退出
        if (!selectField.length) return;
        var button = $('<button type="button" id="toggle-username-btn" class="button" style="margin-left: 5px;">手动输入</button>');
        selectField.after(button);
        manualField.hide();
        button.click(function () {
            if (manualField.is(':visible')) {
                manualField.hide();
                selectField.show();
                button.text('手动输入');
                manualField.val('');
            } else {
                selectField.hide();
                manualField.show();
                button.text('选择岗位编码');
                manualField.focus();
            }
        });
    });
})(django.jQuery);
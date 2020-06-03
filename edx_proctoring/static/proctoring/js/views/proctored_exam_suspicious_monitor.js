var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    var viewHelper = {
        getDateFormat: function(unixTimestamp) {
            if (unixTimestamp) {
                var timeZoneOffset = -60 * (new Date().getTimezoneOffset());
                return new Date((unixTimestamp + timeZoneOffset) * 1000).toString('MMM dd, yyyy h:mmtt');
            }
            else {
                return '---';
            }

        }
    };

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    edx.instructor_dashboard.proctoring.ProctoredExamSuspiciousMonitorView = Backbone.View.extend({
        initialize: function (options) {
            this.setElement($('.suspicious-monitor-container'));
            this.tempate_url = '/static/proctoring/templates/suspicious-monitor.underscore';
            this.course_id = this.$el.data('course-id');
            this.template = null;
            this.data_url = '/api/edx_proctoring/v1/proctored_exam/attempt/session/list/' + this.course_id;
            this.hide_url = '/api/edx_proctoring/v1/proctored_exam/attempt/session/';

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {
            "click .hide-session": "onHideSession"
        },
        getCSRFToken: function () {
            var cookieValue = null;
            var name = 'csrftoken';
            if (document.cookie && document.cookie != '') {
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) == (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({
                url: this.tempate_url,
                dataType: "html"
            }).done(function (template_data) {
                self.template = _.template(template_data);
                self.loadData();
            });
        },
        loadData: function() {
            var self = this;
            $.ajax({
                url: self.data_url,
                dataType: "json"
            }).success(function(data) {
                self.render(data);
            });
        },
        render: function (data) {
            var tplData = {
                proctored_exam_attempts: data,
                data_exists: data.length > 0
            };
            _.extend(tplData, viewHelper);
            var html = this.template(tplData);
            this.$el.html(html);
        },
        onHideSession: function (event) {
            event.preventDefault();

            // confirm the user's intent
            if (!confirm(gettext('Are you sure you want to hide this warning?'))) {
                return;
            }
            $('body').css('cursor', 'wait');
            var $target = $(event.currentTarget);

            var self = this;
            $.ajax({
                type: 'DELETE',
                url: this.hide_url + $target.data("attemptId"),
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                success: function () {
                    // fetch the attempts again.
                    self.loadData();
                    $('body').css('cursor', 'auto');
                }
            });
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamSuspiciousMonitorView = edx.instructor_dashboard.proctoring.ProctoredExamSuspiciousMonitorView;
}).call(this, Backbone, $, _, gettext);

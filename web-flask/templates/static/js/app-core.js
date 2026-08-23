/**
 * 前端公共模块：接口、会话、主题
 */
(function (global) {
    var AppApi = {
        paths: {
            login: '/api/user/login',
            register: '/api/user/register',
            smsSend: '/api/sms/send',
            emailSend: '/api/email/send',
            emailSendBound: '/api/email/send-bound',
            emailSendNew: '/api/email/send-new',
            profile: '/api/user/profile',
            avatar: '/api/user/avatar',
            bindPhone: '/api/user/bind-phone',
            bindEmail: '/api/user/bind-email',
            passwordChange: '/api/user/password/change',
            passwordReset: '/api/user/password/reset',
            passwordResetEmail: '/api/user/password/reset-email',
            adminUsers: '/api/admin/users',
            adminUserDelete: '/api/admin/users/',
            adminUserUnbindPhone: '/api/admin/users/',
            adminUserUnbindEmail: '/api/admin/users/',
            adminUserPassword: '/api/admin/users/',
            adminUserRole: '/api/admin/users/',
            adminUsersPage: '/admin-users.html',
            settings: '/api/user/settings',
            reportPdf: '/api/report/pdf',
            reportEmail: '/api/report/email',
            news: '/api/news',
            llmChat: '/api/llm/chat',
            llmStatus: '/api/llm/status',
            llmConfig: '/api/llm/config',
            models: '/api/models',
            detect: '/api/detect',
            modelData: '/api/model-data',
            experiments: '/api/experiments'
        },
        apiBase: function () {
            var saved = localStorage.getItem('rs_api_base');
            if (saved) return saved.replace(/\/$/, '');
            if (window.location.protocol === 'file:') return 'http://127.0.0.1:5012';
            if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
                return window.location.origin;
            }
            return 'http://127.0.0.1:5012';
        },
        url: function (path) {
            if (path.indexOf('http') === 0) return path;
            var base = AppApi.apiBase();
            return base + (path.charAt(0) === '/' ? path : '/' + path);
        },
        checkService: function () {
            return AppApi.fetchJson('/api/health').then(function (d) {
                if (d.code !== 200) throw new Error('health bad');
                return d.data || {};
            });
        },
        pageUrl: function (page) {
            var base = window.location.pathname || '';
            if (base.indexOf('.html') >= 0) {
                return page.charAt(0) === '/' ? page : page;
            }
            return page;
        },
        headers: function (extra) {
            var h = { 'Content-Type': 'application/json' };
            var u = UserSession.read();
            var name = u ? (u.username || u.id) : '';
            if (u && name) {
                h['X-User-Name'] = name;
            }
            if (extra) {
                for (var k in extra) {
                    h[k] = extra[k];
                }
            }
            return h;
        },
        fetchJson: function (path, options) {
            options = options || {};
            var headers = AppApi.headers(options.headers);
            if (options.body && typeof options.body !== 'string') {
                options.body = JSON.stringify(options.body);
            }
            return fetch(AppApi.url(path), Object.assign({ headers: headers }, options)).then(function (r) {
                return r.text().then(function (t) {
                    var data = null;
                    try {
                        data = t ? JSON.parse(t) : {};
                    } catch (e) {
                        if (!r.ok) {
                            var req = AppApi.url(path);
                            if (t && t.indexOf('<!doctype') >= 0) {
                                throw new Error('接口不存在(HTTP ' + r.status + ')：' + req + '。请先关闭所有旧 python 窗口，双击 web-flask/start.bat 重启服务');
                            }
                            throw new Error(t || ('请求失败 HTTP ' + r.status + '：' + req));
                        }
                        throw new Error('服务器返回格式异常');
                    }
                    return data;
                });
            }).catch(function (err) {
                if (!err || !err.message) {
                    throw new Error('网络请求失败');
                }
                if (err.message === 'Failed to fetch' || err.name === 'TypeError') {
                    throw new Error('无法连接本机服务，请确认后端已启动（Python: http://127.0.0.1:5011 或 Java: http://127.0.0.1:5012）');
                }
                throw err;
            });
        },
        _boundEmailFlight: null,
        _newEmailFlight: null,
        _requestEmailCode: function (primaryPath, body, cdKey) {
            if (cdKey) {
                CodeCooldown.setSending(cdKey, true);
            }
            return AppApi.fetchJson(primaryPath, { method: 'POST', body: body }).catch(function (err) {
                var msg = (err && err.message) || '';
                if (msg.indexOf('404') >= 0 || msg.indexOf('接口不存在') >= 0) {
                    return AppApi.fetchJson(AppApi.paths.emailSend, { method: 'POST', body: body });
                }
                throw err;
            }).finally(function () {
                if (cdKey) {
                    CodeCooldown.setSending(cdKey, false);
                }
            });
        },
        postBoundEmailCode: function (purpose, cdKey) {
            if (AppApi._boundEmailFlight) {
                return AppApi._boundEmailFlight;
            }
            var body = {
                purpose: purpose || 'identity',
                target: 'bound',
                scene: 'identity'
            };
            var u = UserSession.username();
            if (u) body.username = u;
            AppApi._boundEmailFlight = AppApi._requestEmailCode(
                AppApi.paths.emailSendBound, body, cdKey
            ).finally(function () {
                AppApi._boundEmailFlight = null;
            });
            return AppApi._boundEmailFlight;
        },
        postNewEmailCode: function (email, purpose, cdKey) {
            if (AppApi._newEmailFlight) {
                return AppApi._newEmailFlight;
            }
            var body = {
                email: (email || '').trim(),
                purpose: purpose || 'bind',
                target: 'new',
                scene: 'new'
            };
            var u = UserSession.username();
            if (u) body.username = u;
            AppApi._newEmailFlight = AppApi._requestEmailCode(
                AppApi.paths.emailSendNew, body, cdKey
            ).finally(function () {
                AppApi._newEmailFlight = null;
            });
            return AppApi._newEmailFlight;
        },
        downloadPdf: function (path, body) {
            return fetch(AppApi.url(path), {
                method: 'POST',
                headers: AppApi.headers(),
                body: JSON.stringify(body)
            }).then(function (res) {
                var ct = res.headers.get('content-type') || '';
                if (!res.ok || ct.indexOf('json') >= 0) {
                    return res.text().then(function (t) {
                        var msg = '导出失败';
                        try {
                            var data = JSON.parse(t);
                            msg = data.message || msg;
                        } catch (e) {
                            if (t && t.indexOf('<!doctype') >= 0) {
                                msg = '服务异常(HTTP ' + res.status + ')，请确认后端已启动并访问 http://127.0.0.1:5011 或 http://127.0.0.1:5012';
                            } else if (t) {
                                msg = t;
                            }
                        }
                        throw new Error(msg);
                    });
                }
                return res.blob();
            }).catch(function (err) {
                if (!err || !err.message) {
                    throw new Error('网络请求失败');
                }
                if (err.message === 'Failed to fetch' || err.name === 'TypeError') {
                    throw new Error('无法连接本机服务，请确认后端已启动（Python: http://127.0.0.1:5011 或 Java: http://127.0.0.1:5012）');
                }
                throw err;
            });
        }
    };

    var SESSION_KEY = 'rs_detect_session';
    var LEGACY_KEY = 'yyxz_core_user_info';
    var THEME_KEY = 'rs_detect_theme';
    var LAST_DETECT_KEY = 'rs_detect_last_result';

    var UserSession = {
        save: function (user) {
            localStorage.setItem(SESSION_KEY, JSON.stringify(user));
            localStorage.removeItem(LEGACY_KEY);
            if (user && user.theme) {
                ThemeManager.apply(user.theme);
            }
        },
        read: function () {
            var raw = localStorage.getItem(SESSION_KEY);
            if (!raw) {
                raw = localStorage.getItem(LEGACY_KEY);
                if (raw) {
                    try {
                        var legacy = JSON.parse(raw);
                        localStorage.setItem(SESSION_KEY, raw);
                        localStorage.removeItem(LEGACY_KEY);
                        return legacy;
                    } catch (e) {
                        localStorage.removeItem(LEGACY_KEY);
                    }
                }
                return null;
            }
            try {
                return JSON.parse(raw);
            } catch (e) {
                localStorage.removeItem(SESSION_KEY);
                return null;
            }
        },
        clear: function () {
            localStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(LEGACY_KEY);
        },
        loggedIn: function () {
            var u = UserSession.read();
            return u && (u.username || u.id);
        },
        username: function () {
            var u = UserSession.read();
            return u ? (u.username || u.id || '') : '';
        },
        saveLastDetect: function (payload) {
            localStorage.setItem(LAST_DETECT_KEY, JSON.stringify(payload));
        },
        readLastDetect: function () {
            try {
                return JSON.parse(localStorage.getItem(LAST_DETECT_KEY));
            } catch (e) {
                return null;
            }
        }
    };

    var ThemeManager = {
        apply: function (theme) {
            theme = theme || localStorage.getItem(THEME_KEY) || 'default';
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem(THEME_KEY, theme);
        },
        init: function () {
            var u = UserSession.read();
            ThemeManager.apply(u && u.theme ? u.theme : localStorage.getItem(THEME_KEY));
        }
    };

    ThemeManager.init();

    var CODE_CD_SECONDS = 60;
    var CodeCooldown = {
        endsAt: {},
        sending: {},
        tickTimer: null,
        remain: function (key) {
            var end = CodeCooldown.endsAt[key];
            if (!end) return 0;
            var left = Math.ceil((end - Date.now()) / 1000);
            if (left <= 0) {
                delete CodeCooldown.endsAt[key];
                return 0;
            }
            return left;
        },
        disabled: function (key) {
            return CodeCooldown.sending[key] || CodeCooldown.remain(key) > 0;
        },
        setSending: function (key, value) {
            if (!key) return;
            if (value) {
                CodeCooldown.sending[key] = true;
            } else {
                delete CodeCooldown.sending[key];
            }
        },
        label: function (key, text) {
            text = text || '获取验证码';
            if (CodeCooldown.sending[key]) {
                return '发送中...';
            }
            var n = CodeCooldown.remain(key);
            return n > 0 ? (n + '秒后重试') : text;
        },
        start: function (key, seconds) {
            seconds = seconds || CODE_CD_SECONDS;
            CodeCooldown.endsAt[key] = Date.now() + seconds * 1000;
            CodeCooldown._ensureTick();
        },
        clear: function (key) {
            delete CodeCooldown.endsAt[key];
        },
        _ensureTick: function () {
            if (CodeCooldown.tickTimer) return;
            CodeCooldown.tickTimer = setInterval(function () {
                var hasActive = false;
                for (var k in CodeCooldown.endsAt) {
                    if (CodeCooldown.remain(k) > 0) hasActive = true;
                }
                if (!hasActive) {
                    clearInterval(CodeCooldown.tickTimer);
                    CodeCooldown.tickTimer = null;
                }
            }, 500);
        },
        applyResponse: function (key, d) {
            if (d && Number(d.code) === 200) {
                CodeCooldown.start(key);
                return;
            }
            if (d && Number(d.code) === 429) {
                var m = (d.message || '').match(/(\d+)\s*秒/);
                CodeCooldown.start(key, m ? parseInt(m[1], 10) : CODE_CD_SECONDS);
            }
        }
    };

    global.AppApi = AppApi;
    global.UserSession = UserSession;
    global.ThemeManager = ThemeManager;
    global.CodeCooldown = CodeCooldown;
    global.CODE_CD_SECONDS = CODE_CD_SECONDS;
})(window);

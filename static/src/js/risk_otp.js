// Cuenta regresiva de reenvío (throttle 60s) y vigencia (TTL) del código OTP
// de firma. Lee los datetime UTC que renderiza el servidor.
(function () {
    var RESEND_SECONDS = 60;

    function parseUtc(value) {
        if (!value) {
            return null;
        }
        var date = new Date(value.replace(" ", "T") + "Z");
        return isNaN(date.getTime()) ? null : date;
    }

    function pad(n) {
        return (n < 10 ? "0" : "") + n;
    }

    function initResend(button) {
        var sentAt = parseUtc(button.getAttribute("data-otp-sent"));
        if (!sentAt) {
            return;
        }
        var label = button.querySelector(".risk-otp-send-label") || button;
        var original = label.textContent;
        var resendAt = sentAt.getTime() + RESEND_SECONDS * 1000;

        function tick() {
            var remaining = Math.round((resendAt - Date.now()) / 1000);
            if (remaining > 0) {
                button.disabled = true;
                label.textContent = "Reenviar en " + remaining + "s";
                window.setTimeout(tick, 1000);
            } else {
                button.disabled = false;
                label.textContent = original;
            }
        }
        tick();
    }

    function initExpiry(meta) {
        var expiresAt = parseUtc(meta.getAttribute("data-otp-expires"));
        if (!expiresAt) {
            return;
        }
        var base = meta.textContent.trim();

        function tick() {
            var remaining = Math.round((expiresAt.getTime() - Date.now()) / 1000);
            if (remaining > 0) {
                var mm = Math.floor(remaining / 60);
                var ss = remaining % 60;
                meta.textContent = base + " Vence en " + mm + ":" + pad(ss) + ".";
                window.setTimeout(tick, 1000);
            } else {
                meta.textContent = base + " El codigo expiro, solicita uno nuevo.";
            }
        }
        tick();
    }

    function init() {
        var buttons = document.querySelectorAll(".risk-otp-send[data-otp-sent]");
        Array.prototype.forEach.call(buttons, initResend);
        var metas = document.querySelectorAll(".risk-verify-meta[data-otp-expires]");
        Array.prototype.forEach.call(metas, initExpiry);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());

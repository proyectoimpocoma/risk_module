(function () {
    function initRiskSignaturePads() {
        var pads = document.querySelectorAll("[data-signature-pad]");
        if (!pads.length) {
            return;
        }

        function createPad(pad) {
            var name = pad.getAttribute("data-signature-pad");
            var canvas = pad.querySelector("canvas");
            var input = document.getElementById(name + "-signature-input");
            var clearButton = document.querySelector("[data-clear-signature='" + name + "']");
            var studyRadios = document.querySelectorAll("input[name='" + name + "_has_valid_study']");
            var context = canvas.getContext("2d");
            var drawing = false;
            var hasInk = false;

            function resizeCanvas() {
                var existingValue = input.value;
                var ratio = window.devicePixelRatio || 1;
                var rect = canvas.getBoundingClientRect();
                canvas.width = Math.max(1, Math.floor(rect.width * ratio));
                canvas.height = Math.max(1, Math.floor(rect.height * ratio));
                context.setTransform(ratio, 0, 0, ratio, 0, 0);
                context.lineWidth = 2.2;
                context.lineCap = "round";
                context.lineJoin = "round";
                context.strokeStyle = "#1f2933";

                if (existingValue) {
                    var image = new Image();
                    image.onload = function () {
                        context.drawImage(image, 0, 0, rect.width, rect.height);
                    };
                    image.src = existingValue;
                    hasInk = true;
                }
            }

            function point(event) {
                var source = event.touches && event.touches.length ? event.touches[0] : event;
                var rect = canvas.getBoundingClientRect();
                return {
                    x: source.clientX - rect.left,
                    y: source.clientY - rect.top,
                };
            }

            function start(event) {
                if (pad.classList.contains("is-disabled")) {
                    return;
                }
                drawing = true;
                hasInk = true;
                var p = point(event);
                context.beginPath();
                context.moveTo(p.x, p.y);
                event.preventDefault();
            }

            function move(event) {
                if (!drawing) {
                    return;
                }
                var p = point(event);
                context.lineTo(p.x, p.y);
                context.stroke();
                event.preventDefault();
            }

            function end() {
                if (!drawing) {
                    return;
                }
                drawing = false;
                input.value = hasInk ? canvas.toDataURL("image/png") : "";
            }

            function clear() {
                var rect = canvas.getBoundingClientRect();
                context.clearRect(0, 0, rect.width, rect.height);
                input.value = "";
                hasInk = false;
            }

            function syncStudyState() {
                var hasStudy = Array.prototype.some.call(studyRadios, function (radio) {
                    return radio.checked && radio.value === "yes";
                });
                pad.classList.toggle("is-disabled", hasStudy);
                if (hasStudy) {
                    clear();
                }
            }

            canvas.addEventListener("mousedown", start);
            canvas.addEventListener("mousemove", move);
            canvas.addEventListener("mouseup", end);
            canvas.addEventListener("mouseleave", end);
            canvas.addEventListener("touchstart", start, { passive: false });
            canvas.addEventListener("touchmove", move, { passive: false });
            canvas.addEventListener("touchend", end);
            clearButton.addEventListener("click", clear);
            Array.prototype.forEach.call(studyRadios, function (radio) {
                radio.addEventListener("change", syncStudyState);
            });
            window.addEventListener("resize", resizeCanvas);

            resizeCanvas();
            syncStudyState();
        }

        Array.prototype.forEach.call(pads, createPad);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initRiskSignaturePads);
    } else {
        initRiskSignaturePads();
    }
}());

/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.RiskSubmissionVehicle = publicWidget.Widget.extend({
    selector: '.risk-step-page',
    events: {
        'change #has_semi_trailer_toggle': '_onSemiTrailerToggle',
        'click .btn-toggle-password': '_onTogglePassword',
    },

    /**
     * @override
     */
    start: function () {
        this._syncSemiTrailerState();
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onSemiTrailerToggle: function (ev) {
        this._syncSemiTrailerState();
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onTogglePassword: function (ev) {
        ev.preventDefault();
        var $input = this.$('#satellite_password');
        var $icon = this.$(ev.currentTarget).find('i, .material-symbols-outlined');
        
        if ($input.attr('type') === 'password') {
            $input.attr('type', 'text');
            $icon.removeClass('fa-eye').addClass('fa-eye-slash');
            if ($icon.hasClass('material-symbols-outlined')) {
                $icon.text('visibility_off');
            }
            this.$(ev.currentTarget).attr('aria-label', 'Ocultar contraseña');
        } else {
            $input.attr('type', 'password');
            $icon.removeClass('fa-eye-slash').addClass('fa-eye');
            if ($icon.hasClass('material-symbols-outlined')) {
                $icon.text('visibility');
            }
            this.$(ev.currentTarget).attr('aria-label', 'Mostrar contraseña');
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _syncSemiTrailerState: function () {
        var $valueInput = this.$('#has_semi_trailer');
        var $toggle = this.$('#has_semi_trailer_toggle');
        var $plateInput = this.$('#semi_trailer_plate');
        var $plateField = this.$("[data-semi-trailer-field='1']");

        if (!$valueInput.length || !$toggle.length || !$plateInput.length || !$plateField.length) {
            return;
        }

        var enabled = $toggle.prop('checked');
        $valueInput.val(enabled ? "yes" : "no");
        $plateInput.prop('disabled', !enabled);
        $plateInput.prop('required', enabled);
        $plateField.toggleClass("is-disabled", !enabled);

        if (!enabled) {
            $plateInput.val("");
        }
    },
});

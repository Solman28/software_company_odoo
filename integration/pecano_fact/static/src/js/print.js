/** @odoo-module **/
"use strict";

import { registry } from "@web/core/registry";

const actionRegistry = registry.category('actions');

function PecanoFactPrint(parent, action) {
    console.log(action.params.file64)
    printJS({printable: action.params.file64, type: 'pdf', base64: true})
    parent.services.action.doAction({
        'type': 'ir.actions.act_window_close'
    })
    return;
}

actionRegistry.add('print', PecanoFactPrint);
export default PecanoFactPrint;
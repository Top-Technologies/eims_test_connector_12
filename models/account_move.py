import json
import requests
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.fields import Char, One2many
from . import eims_auth
from odoo.exceptions import UserError
from decimal import Decimal, ROUND_HALF_UP
from odoo.addons.eims_test_connector_12.services.crypto_utils import sign_eims_request

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # _sql_constraints = [
    #     ('unique_irn', 'unique(eims_irn)', 'Compliance Error: This IRN has already been used in another invoice.')
    # ]

    eims_receipt_rrn = fields.Char(string="EIMS Receipt RRN")
    eims_receipt_status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed')
    ], default='pending')

    # --- Fields for EIMS Registration ---
    # single
    eims_irn = fields.Char(string="EIMS IRN")
    eims_ack_date = fields.Datetime(string="EIMS Acknowledgement Date")
    eims_signed_invoice = fields.Text("EIMS Signed Invoice (Base64)")
    eims_qr_code = fields.Text("EIMS QR Code (Base64)")
    eims_registered_invoice_count = fields.Integer(
        string='EIMS Logs',
        compute='_compute_eims_registered_invoice_count'
    )

    # bulk
    # eims_bulk_status = fields.Char("EIMS Status")
    eims_callback_message = fields.Text("EIMS Callback Message")
    invoice_number = fields.Char(string="Invoice Number")

    # --- Fields for EIMS Verification ---
    eims_verified = fields.Boolean(string="Verified via EIMS", default=False)
    eims_verified_data = fields.Json(string="Verified Data")
    eims_verification_status = fields.Char(string="Verification Status")
    eims_document_number = fields.Char(string="Document Number")
    eims_document_date = fields.Datetime(string="Document Date")

    # eims_buyer_details
    # eims_buyer_details = fields.Json(string="Buyer Details")
    eims_buyers_tin = fields.Char(string="Buyer TIN")
    eims_buyers_city_code = fields.Char(string="Buyer City")
    eims_buyers_region = fields.Char(string="Buyer Region")
    eims_buyers_wereda = fields.Char(string="Buyer Wereda")
    eims_buyers_vat_number = fields.Char(string="Buyer VAT Number")
    eims_buyers_id_type = fields.Char(string="Buyer ID Type")
    eims_buyers_id_number = fields.Char(string="Buyer ID Number")
    eims_buyers_legal_name = fields.Char(string="Buyer Legal Name")
    eims_buyers_email = fields.Char(string="Buyer Email")
    eims_buyers_phone = fields.Char(string="Buyer Phone")

    # eims_source_system
    eims_source_system = fields.Char(string="Source System")
    eims_cashier_name = fields.Char(string="Cashier Name")
    eims_system_number = fields.Char(string="System Number")
    eims_invoice_counter = fields.Char(string="Invoice Counter")
    eims_sales_person_name = fields.Char(string="Sales Person Name")

    # eims_seller_details
    # eims_seller_details = fields.Json(string="Seller Details")
    eims_seller_tin = fields.Char(string="Seller TIN")
    eims_seller_city_code: Char = fields.Char(string="Seller City")
    eims_seller_region = fields.Char(string="Seller Region")
    eims_seller_wereda = fields.Char(string="Seller Wereda")
    eims_seller_legal_name = fields.Char(string="Seller Legal Name")
    eims_seller_email = fields.Char(string="Seller Email")
    eims_seller_phone = fields.Char(string="Seller Phone")
    eims_seller_tax_center = fields.Char(string="Seller Tax Center")
    eims_seller_vat_number = fields.Char(string="Seller VAT Number")
    eims_seller_house_number = fields.Char(string="Seller House Number")
    eims_seller_locality = fields.Char(string="Seller Locality")

    # eims_value_details
    # eims_value_details = fields.Json(string="Value Details")
    eims_payment_details = fields.Json(string="Payment Details")
    eims_total_value = fields.Float("Total Value")
    eims_tax_value = fields.Float("Tax Value")
    eims_invoice_currency = fields.Char("Currency")

    # eims_payment_details
    eims_payment_mode = fields.Char(string="Payment Mode")
    eims_payment_term = fields.Char(string="Payment Term")

    # eims_document_details
    eims_document_details = fields.Json(string="Document Details")
    eims_document_number = fields.Char(string="Document Number")
    eims_document_date = fields.Datetime(string="Document Date")
    eims_document_type = fields.Char(string="Document Type")
    eims_document_reason = fields.Char(string="Document Reason")

    # eims_transaction_type
    eims_transaction_type = fields.Char(string="Transaction Type")
    eims_reference_details = fields.Json(string="Reference Details")
    eims_previous_irn = fields.Char(string="Previous IRN")
    eims_related_document = fields.Char(string="Related Document")

    # cancel
    eims_cancel_message = fields.Text("Cancellation Message")
    eims_cancelled = fields.Boolean(string="EIMS Cancelled", default=False)
    eims_cancel_date = fields.Datetime(string="EIMS Cancellation Date")
    eims_cancel_log_count = fields.Integer(
        string='EIMS Cancel Log',
        compute='_compute_eims_cancel_log_count'
    )
    eims_receipt_log_count = fields.Integer(
        string='EIMS Receipt Log',
        compute='_compute_eims_receipt_log_count'
    )
    eims_credit_log_count = fields.Integer(
        string='EIMS Credit Log',
        compute='_compute_eims_credit_log_count'
    )
    # reversal_origin_id = fields.Many2one(
    #     'account.move',
    #     string='Original Invoice',
    #     help='The original invoice this credit memo is linked to.'
    # )
    credit_memo_id = fields.Many2one(
        'account.move',
        string='Credit Memo',
        required=True,
        help='Credit Memo linked to this log.'
    )
    original_move_id = fields.Many2one(
        'account.move',
        string='Original Invoice',
        required=True,
        help='The original invoice this credit memo is linked to.'
    )
    last_credit_memo_response = fields.Text(string="Last Credit Memo Response")
    eims_is_debit_note = fields.Boolean(
        string="Is Debit Note", default=False,
        help="Set to True when this invoice is a Debit Note (additional quantities/amounts to an existing invoice)"
    )

    reversal_reason = fields.Char(string='Reversal Reason')
    credit_memo_date = fields.Datetime(string='Credit Memo Date')
    #
    eims_document_number = fields.Integer(string="EIMS Document Number")
    eims_invoice_counter = fields.Integer(string="EIMS Invoice Counter")
    eims_receipt_qr_code = fields.Binary("Receipt QR Code")

    # Bulk
    eims_bulk_response_ids = fields.One2many(
        'eims.bulk.response',
        'invoice_id',
        string='Bulk Responses'
    )
    eims_registered_invoice_ids = fields.One2many(
        'eims.registered.invoice',
        'move_id',
        string='Registered Invoices'
    )
    #
    eims_status = fields.Selection(
        [('pending', 'Pending'),
         ('sent', 'Sent'),
         ('verified', 'Verified'),
         ('cancelled', 'Cancelled'),
         ('error', 'Error')],
        string="EIMS Status",
        default='pending',
        tracking=True
    )

    eims_bulk_response = fields.Text("EIMS Bulk Response")

    def _get_eims_doc_type(self):
        """Return DEB if amount increases, CRE if amount decreases."""
        self.ensure_one()

        original = self.reversed_entry_id
        if not original:
            return "CRE"  # default safety fallback

        original_total = original.amount_total
        new_total = self.amount_total

        return "DEB" if new_total > original_total else "CRE"

    # --- Button to open EIMS Logs ---
    def open_eims_logs(self):
        return {
            'name': 'EIMS Registered Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'eims.registered.invoice',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('move_id', 'in', self.ids)],
        }

    def open_eims_cancel_log(self):
        return {
            'name': 'EIMS Cancel Log',
            'type': 'ir.actions.act_window',
            'res_model': 'eims.cancel.log',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('move_id', 'in', self.ids)],
        }

    def open_eims_receipt_log(self):
        self.ensure_one()
        return {
            'name': 'EIMS Receipt Log',
            'type': 'ir.actions.act_window',
            'res_model': 'eims.receipt.log',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('move_id', 'in', self.ids)],
        }

    def open_eims_credit_log(self):
        self.ensure_one()
        return {
            'name': 'EIMS Credit Log',
            'type': 'ir.actions.act_window',
            'res_model': 'eims.credit.memo.log',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('move_id', 'in', self.ids)],
        }

    @api.depends('line_ids')
    def _compute_eims_registered_invoice_count(self):
        for record in self:
            record.eims_registered_invoice_count = self.env['eims.registered.invoice'].search_count([
                ('move_id', '=', record.id)
            ])

    @api.depends('line_ids')
    def _compute_eims_cancel_log_count(self):
        for record in self:
            record.eims_cancel_log_count = self.env['eims.cancel.log'].search_count([
                ('move_id', '=', record.id)
            ])

    @api.depends('line_ids')
    def _compute_eims_receipt_log_count(self):
        for record in self:
            record.eims_receipt_log_count = self.env['eims.receipt.log'].search_count([
                ('move_id', '=', record.id)
            ])

    @api.depends('line_ids')
    def _compute_eims_credit_log_count(self):
        for record in self:
            record.eims_credit_log_count = self.env['eims.credit.memo.log'].search_count([
                ('move_id', '=', record.id)
            ])

    def _extract_doc_number(self):
        """Extract numeric part from invoice name like 'INV/2025/00041' → 41"""
        try:
            if self.name:
                last_part = self.name.split('/')[-1]
                return int(last_part.lstrip('0') or '0')
        except Exception:
            return 0
        return 0

    # --- Hooks into invoice posting ---
    @api.model
    def create(self, vals):
        invoice = super(AccountMove, self).create(vals)
        # Set default status
        # Auto-send if it's an outgoing invoice already posted
        if invoice.move_type == 'out_invoice' and invoice.state == 'posted':
            try:
                invoice.send_to_eims_single()
            except Exception as e:
                invoice.message_post(body=f"❌ Error sending invoice to EIMS: {e}")
        return invoice

    def action_post_eims(self):
        for move in self:
            # Set default values only for draft invoices being posted
            if move.state == 'draft':
                # 1. Set invoice_date to today if not set
                if not move.invoice_date:
                    move.invoice_date = fields.Date.context_today(move)

                # 2. Set payment term to 'Immediate' if not set
                if not move.invoice_payment_term_id:
                    immediate_payment_term = self.env.ref('account.account_payment_term_immediate',
                                                          raise_if_not_found=False)
                    if immediate_payment_term:
                        move.invoice_payment_term_id = immediate_payment_term

                # 3. & 4. Set excise rate and taxes on invoice lines
                for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                    # Set excise rate to 0 if not set
                    if hasattr(line, 'x_excise_rate') and not line.x_excise_rate:
                        line.x_excise_rate = 0.0

                    # Set taxes to 15% if not set
                    if not line.tax_ids:
                        tax_type = 'sale' if move.is_sale_document(include_receipts=True) else 'purchase'
                        tax_15 = self.env['account.tax'].search([
                            ('company_id', '=', move.company_id.id),
                            ('type_tax_use', '=', tax_type),
                            ('amount', '=', 15)
                        ], limit=1)
                        if tax_15:
                            line.tax_ids = [(6, 0, tax_15.ids)]
        return super().action_post()

    eims_log_id = fields.Many2one('eims.registered.invoice', string="EIMS Log")

    def action_send_to_eims(self):
        self.ensure_one()
        try:
            # 0️⃣ Check if invoice is draft and post it with defaults
            if self.state == 'draft':
                self.action_post_eims()
            # 1️⃣ Auto-post the invoice if not already posted
            if self.state != 'posted':
                _logger.info(f"[EIMS] Auto-posting invoice {self.name}")
                self.action_post()

            # 2️⃣ Send invoice to EIMS
            self.send_to_eims_single()
            _logger.info(f"[EIMS] Invoice {self.name} sent successfully.")
            self.message_post(body=f"📤 Invoice {self.name} sent to EIMS successfully.")

            # 3️⃣ Find or create the EIMS log
            log = self.env['eims.registered.invoice'].search([('move_id', '=', self.id)], limit=1)
            if not log:
                log = self.env['eims.registered.invoice'].create({
                    'move_id': self.id,
                    'eims_irn': self.eims_irn,  # or other fields from response
                    'status': 'success'
                })
                _logger.info(f"[EIMS] Log created for invoice {self.name}: {log.id}")

            # 4️⃣ Verify invoice via the log
            if hasattr(log, 'action_verify_invoice_from_log'):
                log.action_verify_invoice_from_log()
                _logger.info(f"[EIMS] Invoice {self.name} verified via log {log.id}.")
                self.message_post(body=f"✅ Invoice {self.name} verified via EIMS log.")
            else:
                _logger.warning(f"[EIMS] Verification method not found on log {log.id}")


        except Exception as e:
            # Convert error to readable text
            real_error = str(e)
            error_msg = f"❌ Error sending/verifying invoice {self.name} via EIMS:\n{real_error}"
            _logger.error(error_msg)
            # Log full traceback for debugging
            _logger.exception("EIMS send/verify failed")
            self.message_post(body=error_msg)
            # Show REAL error in popup
            raise UserError(real_error)

    def action_send_eims_email(self):
        """Manual button to send EIMS email independently."""
        self.ensure_one()

        # Check if record exists in DB
        if not self.exists():
            msg = f"Invoice {self.id} does not exist or has been deleted."
            self.message_post(body=f"⚠ {msg}")
            _logger.warning(f"[EIMS EMAIL] {msg}")
            return False

        template = self.env.ref(
            "eims_test_connector_12.email_template_eims_invoice",
            raise_if_not_found=False
        )

        if not template:
            raise UserError("Email template for EIMS invoice not found.")

        try:
            template.send_mail(self.id, force_send=True)
            self.message_post(body="📧 EIMS email successfully sent manually.")
            _logger.info(f"[EIMS EMAIL] Manual email sent for invoice {self.name} (ID: {self.id})")
            return True
        except Exception as e:
            self.message_post(body=f"⚠ Manual email could NOT be sent: {e}")
            _logger.error(f"[EIMS EMAIL] Failed to send manual email for invoice {self.name} (ID: {self.id}): {e}")
            return False

    def action_send_cancel_email(self):
        """Send EIMS cancellation email independently."""
        self.ensure_one()
        if self.eims_status != 'cancelled':
            raise UserError("❌ Only cancelled invoices can send the cancellation email.")

        try:
            self._send_eims_cancelled_email()
        except Exception as e:
            self.message_post(body=f"⚠ Failed to send cancellation email: {e}")

    def _send_eims_email(self):
        """Automatically send EIMS email after invoice becomes VERIFIED."""
        self.ensure_one()

        # 🧱 Refresh the record to ensure IRN & Ack Date are correct
        self.env.cr.commit()
        record = self.browse(self.id)

        # 📨 Load email template
        template = self.env.ref(
            "eims_test_connector_12.email_template_eims_invoice",
            raise_if_not_found=False
        )

        if not template:
            raise UserError("Email template for EIMS invoice not found.")

        # 📤 Send email
        try:
            template.send_mail(record.id, force_send=True)
            record.message_post(body="📧 EIMS email sent automatically after verification.")
            _logger.info(f"[EIMS EMAIL] Auto-email sent for invoice {record.name}")
            return True

        except Exception as e:
            record.message_post(body=f"⚠ Email could NOT be sent automatically: {e}")
            _logger.error(f"[EIMS EMAIL] Auto-email FAILED for invoice {record.name}: {e}")
            return False

    def _send_eims_receipt_email(self):
        """Automatically send EIMS receipt email after receipt is successfully created."""
        self.ensure_one()

        # 🧱 Ensure latest values (rrn, qr_code, etc.)
        self.env.cr.commit()
        record = self.browse(self.id)

        # Load receipt email template
        template = self.env.ref(
            "eims_test_connector_12.email_template_eims_receipt",
            raise_if_not_found=False
        )

        if not template:
            raise UserError("Email template for EIMS receipt not found.")

        try:
            template.send_mail(record.id, force_send=True)
            record.message_post(body="📧 EIMS Receipt email sent automatically.")
            _logger.info(f"[EIMS RECEIPT EMAIL] Auto-email sent for invoice {record.name}")
            return True

        except Exception as e:
            record.message_post(body=f"⚠ Could NOT send receipt email: {e}")
            _logger.error(f"[EIMS RECEIPT EMAIL] FAILED for invoice {record.name}: {e}")
            return False

    def _send_eims_cancelled_email(self):

        _logger.warning("📨 Cancel Email Function Triggered for %s", self.name)

        """Send EIMS cancellation email to the customer."""
        template = self.env.ref(
            "eims_test_connector_12.email_template_eims_cancelled",
            raise_if_not_found=True  # Raise immediately if missing
        )

        try:
            mail_id = template.send_mail(self.id, force_send=True, raise_exception=True)
            self.message_post(body=f"📧 EIMS cancellation email sent (Mail ID: {mail_id})")
            _logger.info(f"[EIMS EMAIL] Cancellation email sent for invoice {self.name}, mail_id={mail_id}")
        except Exception as e:
            self.message_post(body=f"⚠ Email could NOT be sent: {e}")
            _logger.error(f"[EIMS EMAIL] Failed to send cancellation email for invoice {self.name}: {e}")

    def action_send_credit_memo_to_eims(self):
        self.ensure_one()

        if self.move_type != 'out_refund':
            raise UserError("This action can only be used on Credit Memos.")

        # --- Validate original invoice ---
        if not self.reversed_entry_id:
            raise UserError("❌ Credit Memo must be linked to an original invoice.")

        if not self.reversed_entry_id.eims_irn:
            raise UserError(
                f"❌ Credit Memo cannot be sent because the original invoice "
                f"{self.reversed_entry_id.name} is not registered/verified in EIMS."
            )

        try:
            # 1️⃣ Auto-post if needed
            if self.state != 'posted':
                _logger.info(f"[EIMS] Auto-posting credit memo {self.name}")
                self.action_post()

            # 2️⃣ Send credit memo
            self.send_credit_memo_to_eims_single()
            self.message_post(body=f"📤 Credit Memo {self.name} sent to EIMS successfully.")
            _logger.info(f"[EIMS] Credit Memo {self.name} sent to EIMS.")

            # 3️⃣ Log using _last_credit_memo_response ONLY
            log = self.env['eims.credit.memo.log'].create({
                'move_id': self.id,  # links to the credit memo itself
                'original_move_id': self.reversed_entry_id.id,
                'eims_irn': self.eims_irn,
                'status': 'submitted',
                'eims_response': self.last_credit_memo_response,
            })

            _logger.info(f"[EIMS] Credit Memo Log created for {self.name}: {log.id}")

            # 4️⃣ Verification
            if hasattr(log, 'action_verify_credit_memo_from_log'):
                log.action_verify_credit_memo_from_log()
                _logger.info(f"[EIMS] Credit Memo {self.name} verified via log {log.id}.")
                self.message_post(body="✅ Credit Memo verified by EIMS.")
            else:
                _logger.warning(f"[EIMS] Verification method missing on log {log.id}")

        except Exception as e:
            msg = f"❌ Error sending/validating Credit Memo {self.name}: {e}"
            _logger.error(msg)
            self.message_post(body=msg)
            raise UserError(_("Failed to submit Credit Memo to EIMS."))

    def verify_eims_invoice(self, irn):

        token, encryption_key = self.env['eims.auth'].get_eims_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        param_obj = self.env['ir.config_parameter'].sudo()
        url = param_obj.get_param('eims.api_single.verify_url',
                                  default='https://core.mor.gov.et/v1/verify')

        response = requests.post(url, json={"irn": irn}, headers=headers, timeout=30)

        try:
            data = response.json()
        except:
            raise UserError("Invalid JSON from EIMS verify service.")

        body = data.get("body") or {}

        # Detect clean cases
        status = body.get("Status")  # A / C / R / U or None

        # If Status missing → treat as UNKNOWN / NEVER REGISTERED
        if not status:
            status = "U"

        return {
            "status": data.get("status"),
            "status_code": data.get("statusCode"),
            "message": data.get("message", ""),
            "eims_status": status,
            "raw": data
        }

    def send_to_eims_single(self):

        status_mapping = {
            "A": "verified",  # Active → Verified
            "C": "cancelled",  # Cancelled
            "R": "rejected",  # Rejected
            "U": "unknown",  # Unknown / Not found
        }
        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()

        for record in self:

            # ---------------------------
            # BASIC VALIDATION
            # ---------------------------
            if record.move_type != 'out_invoice':
                continue

            # Allowed:
            # - posted invoices (new)
            # - cancelled invoices WITH IRN (resend)
            if record.state not in ['posted', 'cancel'] and not record.eims_irn:
                raise UserError("❌ Only POSTED invoices or CANCELLED invoices with IRN can be sent to EIMS.")

            # ---------------------------
            # IRC-N08 VALIDATE BUYER TIN & LEGAL NAME
            # ---------------------------
            buyer = record.partner_id

            # Legal Name
            if not buyer.name or buyer.name.strip() == "" or buyer.name.upper() in ["ABCDEFG", "ABCDEF", "XXXXXX"]:
                raise UserError("❌ Invalid Buyer Legal Name.\n\nPlease enter a valid registered buyer name.")

            # TIN required only for companies (B2B), not for individuals (B2C)
            if buyer.company_type == "company":
                if not buyer.eims_tin:
                    raise UserError("❌ Buyer TIN is missing. A valid 10-digit TIN is required for company customers.")

                # Invalid TIN patterns
                invalid_tins = ["0000000000", "000000000", "1111111111", "1234567890"]
                if buyer.eims_tin in invalid_tins:
                    raise UserError("❌ Invalid Buyer TIN. Cannot use placeholder values like 0000000000.")

                # TIN must be numeric 10 digits
                if not buyer.eims_tin.isdigit() or len(buyer.eims_tin) != 10:
                    raise UserError("❌ Buyer TIN must be a 10-digit numeric value.")

            # ---------------------------
            # VERIFY BEFORE RESENDING
            # ---------------------------
            if record.eims_irn:

                verify_res = record.verify_eims_invoice(record.eims_irn)
                eims_status_raw = verify_res.get("eims_status")
                mapped_status = status_mapping.get(eims_status_raw, "unknown")

                # --- 1) ACTIVE / VERIFIED ---
                if eims_status_raw == "A":
                    raise UserError("❌ Invoice is ACTIVE in EIMS. You cannot resend unless it is cancelled.")

                # --- 2) CANCELLED → allowed ---
                if eims_status_raw == "C":
                    record.message_post(body="ℹ EIMS: Invoice is CANCELLED. Resending allowed.")

                # --- 3) REJECTED → allowed ---
                elif eims_status_raw == "R":
                    record.message_post(body="ℹ EIMS: Invoice was REJECTED. Resending allowed.")

                # --- 4) UNKNOWN → invoice never registered properly ---
                elif eims_status_raw == "U":
                    record.message_post(body="ℹ EIMS: Invoice not found (UNKNOWN). Sending as new.")

                # Anything else → allow but warn
                else:
                    record.message_post(body=f"⚠ Unknown verify status: {eims_status_raw}. Proceeding to send.")

            # ---------------------------
            # NORMAL SEND PROCESS
            # ---------------------------
            try:
                token, encryption_key = self.env['eims.auth'].get_eims_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }

                request_payload = record.prepare_eims_payload_single()

                # 2️⃣ SIGN request (service layer)
                signed_payload = sign_eims_request(request_payload)

                # 3️⃣ Send
                param_obj = self.env['ir.config_parameter'].sudo()
                url = param_obj.get_param('eims.api_single.register_url',
                                          default='https://core.mor.gov.et/v1/register')
                response = http.post(
                    url,
                    headers=headers,
                    json=signed_payload,
                    timeout=(5, 60)  # (Connect timeout, Read timeout)
                )

                res_json = response.json()

                _logger.info("==== EIMS Raw Response ====")
                _logger.info(json.dumps(res_json, indent=2))
                _logger.info("===========================")

                # SUCCESS
                if response.status_code == 200 and res_json.get("statusCode") == 200:

                    body = res_json.get("body", {})

                    record.eims_irn = body.get("irn")
                    record.eims_signed_invoice = body.get("signedInvoice")
                    record.eims_qr_code = body.get('signedQR')

                    # Map the status
                    raw_status = body.get("status")
                    mapped_status = status_mapping.get(raw_status, "unknown")
                    record.eims_status = mapped_status
                    _logger.info(f"[EIMS] Status Raw: {raw_status} → Mapped: {mapped_status}")

                    # Handle ackDate
                    raw = body.get("ackDate")
                    if raw:
                        clean = raw.split('Z')[0].split('[')[0]
                        if '.' in clean:
                            clean = clean.split('.')[0]
                        try:
                            record.eims_ack_date = datetime.strptime(clean, '%Y-%m-%dT%H:%M:%S')
                        except:
                            record.eims_ack_date = raw

                    # Log success
                    # Populate all fields from EIMS response using helper method
                    record._populate_fields_from_eims_body(body)
                    
                    # Set fields that come from payload, not response
                    company = self.env.company
                    transaction_type = record._get_transaction_type(record.partner_id)
                    record.eims_transaction_type = transaction_type
                    record.eims_document_type = "INV"
                    record.eims_payment_mode = "CASH"
                    record.eims_seller_vat_number = company.eims_vat_number or ""
                    
                    # Get previous IRN (last registered invoice before this one)
                    previous_log = self.env['eims.registered.invoice'].search([
                        ('move_id', '!=', record.id),
                        ('eims_irn', '!=', False),
                        ('status', '=', 'success'),
                    ], order='create_date desc', limit=1)
                    record.eims_previous_irn = previous_log.eims_irn if previous_log else ""

                    # Log success with all populated fields
                    self.env['eims.registered.invoice'].create({
                        "move_id": record.id,
                        "partner_id": record.partner_id.id,
                        "eims_irn": record.eims_irn,
                        "ack_date": record.eims_ack_date,
                        "status": "success",
                        "amount_total": record.amount_total,
                        "currency_id": record.currency_id.id,
                        "eims_response": json.dumps(res_json, indent=2),
                        # Buyer details
                        "eims_buyers_tin": record.eims_buyers_tin,
                        "eims_buyers_city_code": record.eims_buyers_city_code,
                        "eims_buyers_region": record.eims_buyers_region,
                        "eims_buyers_wereda": record.eims_buyers_wereda,
                        "eims_buyers_id_type": record.eims_buyers_id_type,
                        "eims_buyers_id_number": record.eims_buyers_id_number,
                        "eims_buyers_legal_name": record.eims_buyers_legal_name,
                        "eims_buyers_email": record.eims_buyers_email,
                        "eims_buyers_phone": record.eims_buyers_phone,
                        # Seller details
                        "eims_seller_tin": record.eims_seller_tin,
                        "eims_seller_city_code": record.eims_seller_city_code,
                        "eims_seller_region": record.eims_seller_region,
                        "eims_seller_wereda": record.eims_seller_wereda,
                        "eims_seller_legal_name": record.eims_seller_legal_name,
                        "eims_seller_email": record.eims_seller_email,
                        "eims_seller_phone": record.eims_seller_phone,
                        "eims_seller_tax_center": record.eims_seller_tax_center,
                        "eims_seller_vat_number": record.eims_seller_vat_number,
                        "eims_seller_house_number": record.eims_seller_house_number,
                        "eims_seller_locality": record.eims_seller_locality,
                        # Value details
                        "eims_total_value": record.eims_total_value,
                        "eims_tax_value": record.eims_tax_value,
                        "eims_invoice_currency": record.eims_invoice_currency,
                        # Payment details
                        "eims_payment_mode": record.eims_payment_mode,
                        "eims_payment_term": record.eims_payment_term,
                        # Source system
                        "eims_source_system": record.eims_source_system,
                        "eims_cashier_name": record.eims_cashier_name,
                        "eims_system_number": record.eims_system_number,
                        "eims_invoice_counter": record.eims_invoice_counter,
                        "eims_sales_person_name": record.eims_sales_person_name,
                        # Document details
                        "eims_document_number": record.eims_document_number,
                        "eims_document_date": record.eims_document_date,
                        "eims_document_type": record.eims_document_type,
                        "eims_document_reason": record.eims_document_reason,
                        # Transaction details
                        "eims_transaction_type": record.eims_transaction_type,
                        "eims_reference_details": record.eims_reference_details,
                        "eims_previous_irn": record.eims_previous_irn,
                        "eims_related_document": record.eims_related_document,
                        # Base64 data
                        "eims_signed_invoice": record.eims_signed_invoice,
                        "eims_qr_code": record.eims_qr_code,
                        "eims_status": mapped_status,
                    })

                    record.message_post(
                        body=f"✅ EIMS Submission Successful\nIRN: {record.eims_irn}\nAck Date: {record.eims_ack_date}"
                    )

                    # ----------------------------------------------------
                    # 📧 SEND EMAIL AFTER VERIFIED (ACTIVE) STATUS
                    # ----------------------------------------------------
                    if record.eims_status == "verified":
                        try:
                            record._send_eims_email()
                        except Exception as email_err:
                            record.message_post(body=f"⚠ Email could NOT be sent: {email_err}")

                    continue

                # FAILURE
                else:
                    self.env['eims.registered.invoice'].create({
                        "move_id": record.id,
                        "partner_id": record.partner_id.id,
                        "status": "failed",
                        "amount_total": record.amount_total,
                        "currency_id": record.currency_id.id,
                        "eims_response": json.dumps(res_json, indent=2)
                    })
                    record.message_post(body=f"❌ Single EIMS Failed: {res_json}")




            except Exception as e:
                self.eims_receipt_status = 'failed'
                self.message_post(body=f"⚠️ Error creating receipt: {repr(e)}")
                _logger.error(f"EIMS Receipt Error for Invoice {self.name}: {repr(e)}")
                raise UserError(_("Failed to create EIMS INV. Check logs."))

    def _populate_fields_from_eims_body(self, body):
        """
        Centralized method to populate invoice fields from EIMS response body.
        Called by both registration and verification flows.
        """
        # Parse all sections from EIMS response
        buyer_details = body.get("BuyerDetails", {})
        seller_details = body.get("SellerDetails", {})
        value_details = body.get("ValueDetails", {})
        payment_details = body.get("PaymentDetails", {})
        source_system = body.get("SourceSystem", {})
        document_details = body.get("DocumentDetails", {})
        transaction_details = body.get("TransactionDetails", {})
        reference_details = body.get("ReferenceDetails", {})  # At root level!

        # Buyer Details
        self.eims_buyers_tin = buyer_details.get("Tin") or ""
        self.eims_buyers_city_code = buyer_details.get("City") or ""
        self.eims_buyers_region = buyer_details.get("Region") or ""
        self.eims_buyers_wereda = buyer_details.get("Wereda") or ""
        self.eims_buyers_vat_number = buyer_details.get("VatNumber") or ""
        self.eims_buyers_id_type = buyer_details.get("IdType") or ""
        self.eims_buyers_id_number = buyer_details.get("IdNumber") or ""
        self.eims_buyers_legal_name = buyer_details.get("LegalName") or ""
        self.eims_buyers_email = buyer_details.get("Email") or ""
        self.eims_buyers_phone = buyer_details.get("Phone") or ""

        # Seller Details
        self.eims_seller_tin = seller_details.get("Tin") or ""
        self.eims_seller_city_code = seller_details.get("City") or ""
        self.eims_seller_region = seller_details.get("Region") or ""
        self.eims_seller_wereda = seller_details.get("Wereda") or ""
        self.eims_seller_legal_name = seller_details.get("LegalName") or ""
        self.eims_seller_email = seller_details.get("Email") or ""
        self.eims_seller_phone = seller_details.get("Phone") or ""
        self.eims_seller_tax_center = str(seller_details.get("TaxCenter") or "")  # Convert to string
        self.eims_seller_vat_number = seller_details.get("VatNumber") or ""  # Mixed case, not all caps!
        self.eims_seller_house_number = seller_details.get("HouseNumber") or ""  # Might not exist in response
        self.eims_seller_locality = seller_details.get("Locality") or ""

        # Value Details
        self.eims_total_value = value_details.get("TotalValue") or 0.0
        self.eims_tax_value = value_details.get("TaxValue") or 0.0
        self.eims_invoice_currency = value_details.get("InvoiceCurrency") or ""

        # Payment Details
        self.eims_payment_mode = payment_details.get("Mode") or ""  # Fixed: "Mode" not "PaymentMode"
        self.eims_payment_term = payment_details.get("PaymentTerm") or ""

        # Source System
        self.eims_source_system = source_system.get("SystemType") or ""
        self.eims_cashier_name = source_system.get("CashierName") or ""
        self.eims_system_number = source_system.get("SystemNumber") or ""
        self.eims_invoice_counter = source_system.get("InvoiceCounter") or ""
        self.eims_sales_person_name = source_system.get("SalesPersonName") or ""

        # Document Details
        self.eims_document_number = document_details.get("DocumentNumber") or ""
        self.eims_document_type = document_details.get("Type") or ""
        self.eims_document_reason = document_details.get("Reason") or ""
        
        # Parse document date if available
        doc_date_str = document_details.get("Date")
        if doc_date_str:
            try:
                self.eims_document_date = datetime.strptime(doc_date_str, "%d-%m-%YT%H:%M:%S")
            except:
                pass

        # Transaction Type - At root level of body!
        self.eims_transaction_type = body.get("TransactionType") or ""  # Not in TransactionDetails!
        
        # Reference Details - At root level of body!
        self.eims_previous_irn = reference_details.get("PreviousIrn") or ""  # Fixed: lowercase 'rn'
        self.eims_related_document = reference_details.get("RelatedDocument") or ""  # Fixed: lowercase 'rd'

    # Generate Credit and debit memo
    def send_credit_memo_to_eims_single(self):

        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        for record in self:
            if record.move_type != 'out_refund':
                continue  # Only credit memos

            # -------------------------
            # Validate original invoice
            # -------------------------
            if not record.reversed_entry_id or not record.reversed_entry_id.eims_irn:
                raise UserError(
                    f"❌ Credit Memo cannot be sent because the original invoice "
                    f"{record.reversed_entry_id.name if record.reversed_entry_id else 'None'} "
                    "is not registered/verified in EIMS."
                )

            # -------------------------
            # Prepare payload
            # -------------------------

            # request_payload = record.prepare_eims_payload_single()
            try:
                # -------------------------
                # Send to EIMS
                # -------------------------
                token, encryption_key = self.env['eims.auth'].get_eims_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }

                request_payload = record.prepare_eims_payload_credit_memo()

                # 2️⃣ SIGN request (service layer)
                signed_payload = sign_eims_request(request_payload)

                param_obj = self.env['ir.config_parameter'].sudo()
                url = param_obj.get_param('eims.api_single.register_url',
                                          default='https://core.mor.gov.et/v1/register')

                response = http.post(url, headers=headers, json=signed_payload, timeout=(5, 60))
                res_json = response.json()

                # Store response for logging in action function
                record.last_credit_memo_response = json.dumps(res_json, indent=2)

                # -------------------------
                # SUCCESS
                # -------------------------
                if response.status_code == 200 and res_json.get("statusCode") == 200:
                    body = res_json.get("body", {})
                    record.eims_irn = body.get("irn")
                    record.eims_status = "verified"

                    # Log success
                    self.env['eims.credit.memo.log'].create({
                        'move_id': record.id,  # credit memo itself
                        'original_move_id': record.reversed_entry_id.id,  # original invoice
                        'credit_memo_irn': record.eims_irn,
                        'status': 'submitted',
                        'partner_id': record.partner_id.id,
                        'eims_response': record.last_credit_memo_response,
                    })

                    record.message_post(
                        body=f"✅ Credit Memo sent to EIMS. IRN: {record.eims_irn}"
                    )

                    # ----------------------------------------------------
                    # 📧 SEND EMAIL AFTER VERIFIED (ACTIVE) STATUS
                    # ----------------------------------------------------
                    if record.eims_status == "verified":
                        try:
                            record._send_eims_email()
                        except Exception as email_err:
                            record.message_post(body=f"⚠ Email could NOT be sent: {email_err}")

                    continue

                # -------------------------
                # FAILURE
                # -------------------------
                self.env['eims.credit.memo.log'].create({
                    'move_id': record.id,  # credit memo itself
                    'original_move_id': record.reversed_entry_id.id,
                    'status': 'failed',
                    'partner_id': record.partner_id.id,
                    'eims_response': record.last_credit_memo_response,
                })

                record.message_post(
                    body=f"❌ Failed to send Credit Memo: {record.last_credit_memo_response}"
                )

            except Exception as e:
                _logger.exception("CREDIT MEMO ERROR DETAILS:")
                record.message_post(body=f"⚠ Error sending Credit Memo: {repr(e)}")
                raise UserError(("Failed to send Credit Memo to EIMS. Check logs."))
        # Generate Sales Receipt

    def action_create_eims_receipt(self):

        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        self.ensure_one()
        company = self.env.company
        partner = self.partner_id
        if not self.eims_irn:
            raise UserError(("Invoice has not been sent to EIMS yet."))

        # ❌ Check if invoice is cancelled
        if self.eims_status == 'cancelled':
            raise UserError("Cannot generate receipt: this invoice has been CANCELLED in EIMS.")

        try:
            # Prepare payload
            payload = {
                "ReceiptNumber": "REC1234567890123466",
                "ReceiptType": "Sales Receipts",
                "Reason": "Payment for Invoice",
                "ReceiptDate": self.invoice_date.strftime('%Y-%m-%dT%H:%M:%S') + "+03:00",
                "ReceiptCounter": "12335",
                "ManualReceiptNumber": "98766",
                "SourceSystemType": "POS",
                "SourceSystemNumber": company.eims_system_number,
                "ReceiptCurrency": self.currency_id.name,
                "CollectedAmount": self.amount_total,
                "SellerTIN": company.eims_tin,
                "Invoices": [
                    {
                        "InvoiceIRN": self.eims_irn,
                        "PaymentCoverage": "FULL",
                        "InvoicePaidAmount": self.amount_total,
                        "TotalAmount": self.amount_total,
                    }
                ],
                "TransactionDetails": {
                    "ModeOfPayment": "CASH",
                    "CollectorName": self.env.user.name,
                    "PaymentServiceProvider": "Bank",
                    "AccountNumber": "123456789",
                    "TransactionNumber": "TRX987654322"
                }
            }

            # Call EIMS API
            token, encryption_key = self.env['eims.auth'].get_eims_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            param_obj = self.env['ir.config_parameter'].sudo()
            url = param_obj.get_param('eims.api_sales.receipt_url',
                                      default='https://core.mor.gov.et/v1/receipt/sales')

            # ⃣ SIGN request (service layer)
            signed_payload = sign_eims_request(payload)

            response = http.post(url, headers=headers, json=signed_payload, timeout=(5, 60))
            res_json = response.json()

            _logger.info("==== EIMS Receipt Response ====")
            _logger.info(json.dumps(res_json, indent=2))
            _logger.info("==============================")

            # After a successful API call
            if response.status_code == 200 and res_json.get("statusCode") == 200:
                body = res_json.get("body", {})
                self.eims_receipt_status = 'success'
                self.eims_receipt_rrn = body.get("rrn")
                self.eims_receipt_qr_code = body.get("qr")

                # Log in EIMS Receipt Log
                self.env['eims.receipt.log'].create({
                    "move_id": self.id,
                    "partner_id": self.partner_id.id,
                    "rrn": self.eims_receipt_rrn,
                    "receipt_date": self.invoice_date,
                    "status": 'success',
                    "amount_total": self.amount_total,
                    "currency_id": self.currency_id.id,
                    "eims_receipt_qr_code": body.get("qr"),
                    "eims_response": json.dumps(res_json, indent=2)
                })

                self.message_post(body=f"✅ Receipt created successfully. RRN: {self.eims_receipt_rrn}")

                # 🔔 Auto send receipt email
                if self.eims_receipt_status == "success":
                    try:
                        self._send_eims_receipt_email()
                    except Exception as e:
                        self.message_post(body=f"⚠ Receipt auto-email failed: {e}")

            # On failure
            else:
                self.eims_receipt_status = 'failed'

                self.env['eims.receipt.log'].create({
                    "move_id": self.id,
                    "partner_id": self.partner_id.id,
                    "status": 'failed',
                    "amount_total": self.amount_total,
                    "currency_id": self.currency_id.id,
                    "eims_response": json.dumps(res_json, indent=2)
                })

                error_msg = f"❌ Receipt creation failed: {json.dumps(res_json)}"
                self.message_post(body=error_msg)
                
                # NEW: Raise UserError so user sees it
                body_msg = res_json.get('body') or res_json.get('message') or "Unknown Error"
                raise UserError(f"Receipt Creation Failed!\nReason: {body_msg}")

        except Exception as e:
            self.eims_receipt_status = 'failed'
            self.message_post(body=f"⚠️ Error creating receipt: {repr(e)}")
            _logger.error(f"EIMS Receipt Error for Invoice {self.name}: {repr(e)}")
            raise UserError(_("Failed to create EIMS receipt. Check logs."))

    # --- Verify Invoice via EIMS ---

    def action_verify_invoice(self):
        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        self.ensure_one()
        if not self.eims_irn:
            raise UserError("Invoice does not have an IRN yet.")

        try:
            token, encryption_key = self.env['eims.auth'].get_eims_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "*/*"
            }
            payload = {"irn": self.eims_irn}
            signed_payload = sign_eims_request(payload)
            param_obj = self.env['ir.config_parameter'].sudo()
            url = param_obj.get_param('eims.api_single.verify_url',
                                      default='https://core.mor.gov.et/v1/verify')
            response = http.post(url, json=signed_payload, headers=headers, timeout=(5, 30))
            data = response.json()

            if data.get("statusCode") == 200 and data.get("message") == "SUCCESS":
                body = data.get("body", {})

                self.eims_verified = True
                self.eims_verified_data = body or {}
                self.eims_verification_status = body.get("status", body.get("Status", "ACTIVE"))
                # self.eims_version = body.get("version", "1")
                # self.eims_item_list = body.get("ItemList", {})
                self.eims_document_number = body.get("DocumentDetails", {}).get("DocumentNumber")
                doc_date = body.get("DocumentDetails", {}).get("Date")
                if doc_date:
                    self.eims_document_date = datetime.strptime(doc_date, "%d-%m-%YT%H:%M:%S")

                val = body.get("ValueDetails", {})
                self.eims_total_value = val.get("TotalValue") or 0.0
                self.eims_tax_value = val.get("TaxValue") or 0.0
                self.eims_invoice_currency = val.get("InvoiceCurrency") or ""

                val = body.get("BuyerDetails", {})
                self.eims_buyers_tin = val.get("Tin") or ""
                self.eims_buyers_city_code = val.get("City") or ""
                self.eims_buyers_region = val.get("Region") or ""
                self.eims_buyers_wereda = val.get("Wereda") or ""
                self.eims_buyers_id_type = val.get("IdType") or ""
                self.eims_buyers_id_number = val.get("IdNumber") or ""
                self.eims_buyers_legal_name = val.get("LegalName") or ""
                self.eims_buyers_email = val.get("Email") or ""
                self.eims_buyers_phone = val.get("Phone") or ""

                val = body.get("SourceSystem", {})
                self.eims_source_system = val.get("SourceSystem") or ""
                self.eims_cashier_name = val.get("CashierName") or ""
                self.eims_system_number = val.get("SystemNumber") or ""
                self.eims_invoice_counter = val.get("InvoiceCounter") or ""
                self.eims_sales_person_name = val.get("SalesPersonName") or ""

                val = body.get("SellerDetails", {})
                self.eims_seller_tin = val.get("Tin") or ""
                self.eims_seller_city_code = val.get("City") or ""
                self.eims_seller_region = val.get("Region") or ""
                self.eims_seller_wereda = val.get("Wereda") or ""
                # self.eims_seller_id_type = val.get("IdType") or ""
                # self.eims_seller_id_number = val.get("IdNumber") or ""
                self.eims_seller_legal_name = val.get("LegalName") or ""
                self.eims_seller_email = val.get("Email") or ""
                self.eims_seller_phone = val.get("Phone") or ""

                val = body.get("PaymentDetails", {})
                self.eims_payment_mode = val.get("PaymentMode") or ""
                self.eims_payment_term = val.get("PaymentTerm") or ""

                val = body.get("DocumentDetails", {})
                self.eims_document_details = val.get("DocumentDetails", {}) or ""
                self.eims_document_date = val.get("Date") or ""
                self.eims_document_type = val.get("Type") or ""
                self.eims_document_reason = val.get("Reason") or ""
                self.eims_document_number = val.get("DocumentNumber") or ""

                val = body.get("TransactionDetails", {})
                self.eims_transaction_type = val.get("TransactionType") or ""
                self.eims_reference_details = val.get("ReferenceDetails", {}) or ""
                self.eims_previous_irn = val.get("PreviousIRN") or ""

            self.message_post(
                body=f"✅ Invoice Verified via EIMS<br/>"
                     f"IRN: {self.eims_irn}<br/>"
                     f"Document No: {self.eims_document_number}"
            )

            log = self.env['eims.registered.invoice'].search([('move_id', '=', self.id)], limit=1)
            values = {
                "partner_id": self.partner_id.id,
                "eims_irn": self.eims_irn,
                "ack_date": self.eims_ack_date,
                "status": "success",
                "amount_total": self.amount_total,
                "currency_id": self.currency_id.id,
                "eims_verified": True,
                "eims_verified_data": self.eims_verified_data,
                # "eims_buyer_details": self.eims_buyer_details,
                # "eims_seller_details": self.eims_seller_details,
                # "eims_value_details": self.eims_value_details,
                "eims_total_value": self.eims_total_value,
                "eims_tax_value": self.eims_tax_value,
                "eims_invoice_currency": self.eims_invoice_currency,
                # "eims_payment_details": self.eims_payment_details,
                "eims_document_number": self.eims_document_number,
                "eims_document_date": self.eims_document_date,
                "eims_response": json.dumps(data, indent=2),
                "eims_qr_code": self.eims_qr_code,
                "eims_signed_invoice": self.eims_signed_invoice,
                "eims_buyers_tin": self.eims_buyers_tin,
                "eims_buyers_city_code": self.eims_buyers_city_code,
                "eims_buyers_region": self.eims_buyers_region,
                "eims_buyers_wereda": self.eims_buyers_wereda,
                "eims_buyers_id_type": self.eims_buyers_id_type,
                "eims_buyers_id_number": self.eims_buyers_id_number,
                "eims_buyers_legal_name": self.eims_buyers_legal_name,
                "eims_buyers_email": self.eims_buyers_email,
                "eims_buyers_phone": self.eims_buyers_phone,
                "eims_seller_tin": self.eims_seller_tin,
                "eims_seller_city_code": self.eims_seller_city_code,
                "eims_seller_region": self.eims_seller_region,
                "eims_seller_wereda": self.eims_seller_wereda,
                "eims_seller_legal_name": self.eims_seller_legal_name,
                "eims_seller_email": self.eims_seller_email,
                "eims_seller_phone": self.eims_seller_phone,
                "eims_payment_mode": self.eims_payment_mode,
                "eims_payment_term": self.eims_payment_term,
                "eims_source_system": self.eims_source_system,
                "eims_cashier_name": self.eims_cashier_name,
                "eims_system_number": self.eims_system_number,
                "eims_invoice_counter": self.eims_invoice_counter,
                "eims_sales_person_name": self.eims_sales_person_name,
                # "eims_document_details": self.eims_document_details,
                "eims_transaction_type": self.eims_transaction_type,
                "eims_reference_details": self.eims_reference_details,
                "eims_previous_irn": self.eims_previous_irn,

            }
            if log:
                log.write(values)
            else:
                self.env['eims.registered.invoice'].create(values)

        except Exception as e:
            self.message_post(body=f"⚠️ Verification Error: {str(e)}")

    def action_bulk_send_to_eims(self):
        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        """Bulk send all selected invoices (already filtered in view) and log responses individually."""
        if not self:
            raise UserError("No invoices selected for bulk sending.")

        company = self.env.company

        # ----------------------------
        # Authenticate
        # ----------------------------
        try:
            token, encryption_key = self.env['eims.auth'].get_eims_token()
        except Exception as e:
            raise UserError(f"❌ Failed to authenticate with EIMS: {str(e)}")

        # ----------------------------
        # Callback URL
        # ----------------------------
        callback_url = self.env["ir.config_parameter"].sudo().get_param(
            "eims.callback.url"
        ) or "https://91.99.115.196/eims/bulk-callback"

        # ----------------------------
        # Headers
        # ----------------------------
        headers = {
            "Authorization": f"Bearer {token}",
            "TIN": company.eims_tin,
            "SystemNumber": company.eims_system_number,
            "CallbackURL": callback_url,
            "Content-Type": "application/json",
        }

        # ----------------------------
        # Build payload list
        # ----------------------------
        payload_list = []
        for invoice in self:
            if invoice.move_type != "out_invoice" or invoice.state != "posted":
                continue

            payload_item = invoice.prepare_eims_payload_single()

            # ✅ Correct path
            doc_no = str(payload_item["DocumentDetails"]["DocumentNumber"])

            # Save mapping for callback
            self.env['eims.bulk.mapping'].sudo().create({
                'document_number': doc_no,
                'invoice_id': invoice.id,
            })

            _logger.warning("📌 Mapping saved: document_number=%s (type=%s)",
                            doc_no, type(doc_no).__name__)

            payload_list.append(payload_item)

        if not payload_list:
            raise UserError("No valid invoices to send to EIMS.")

        # ----------------------------
        # Call EIMS bulk API
        # ----------------------------
        try:
            signed_payload_list = sign_eims_request(payload_list)
            response = http.post(callback_url, headers=headers, json=signed_payload_list, timeout=(5, 60))
            res_json = response.json()

            _logger.info("📨 RAW EIMS Bulk Response: %s", json.dumps(res_json, indent=4))
            conversation_id = res_json.get("conversationId", "pending")

            # Log each invoice individually
            for invoice in self:
                invoice.message_post(
                    body=f"📨 Bulk EIMS sent. Awaiting callback.\nConversation ID: {conversation_id}"
                )

        except Exception as e:
            for invoice in self:
                invoice.message_post(body=f"❌ Bulk EIMS Error: {str(e)}")
            raise UserError(f"❌ Bulk EIMS Failed: {str(e)}")

    def action_view_unregistered_eims_invoices(self):
        """Show invoices missing IRN and not expired (within 72 hours)."""
        limit_time = fields.Datetime.now() - timedelta(hours=72)

        return {
            'name': 'Unregistered EIMS Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('eims_irn', '=', False),
                ('invoice_date', '>=', limit_time),
                ('eims_status', '=', 'pending'),  # Only show invoices that are still pending
            ],
            'context': {'default_move_type': 'out_invoice'},
        }

    # eims_active = fields.Boolean(
    #     string="EIMS Active",
    #     compute='_compute_eims_active',
    #     store=True,  # <-- make it stored in DB
    # )

    # def action_view_sent_eims_invoices(self):
    #     """Return only invoices with IRN that are still active in EIMS."""
    #     sent_invoices = self.search([('move_type', '=', 'out_invoice'), ('eims_irn', '!=', False)])
    #     active_invoices = self.browse()
    #     for invoice in sent_invoices:
    #
    #         try:
    #             response = requests.post(
    #                 'http://core.mor.gov.et/v1/verify',
    #                 json={'irn': invoice.eims_irn},
    #                 timeout=5
    #             ).json()
    #             if response.get('status') != 'Error':  # Only include non-canceled invoices
    #                 active_invoices |= invoice
    #         except Exception:
    #             continue
    #
    #     return {
    #         'name': 'Sent EIMS Invoices',
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.move',
    #         'view_mode': 'list,form',
    #         'domain': [('id', 'in', active_invoices.ids)],
    #         'context': {'default_move_type': 'out_invoice'},
    #     }

    # @api.model
    # def _verify_eims_status(self, irn):
    #     """Helper: Verify status from EIMS"""
    #     url = "http://core.mor.gov.et/v1/verify"
    #
    #     try:
    #         response = requests.post(url, json={"irn": irn}, timeout=10)
    #         return response.json()
    #     except Exception as e:
    #         return {"status": "Error", "message": str(e)}
    def action_view_sent_eims_invoices(self):
        """Return only invoices that have been sent to EIMS and are still ACTIVE (locally)."""

        # Fetch invoices that have IRN and are ACTIVE in EIMS
        active_invoices = self.search([
            ('move_type', '=', 'out_invoice'),
            ('eims_irn', '!=', False),
            ('eims_status', '=', 'verified')  # Only ACTIVE invoices
        ])

        return {
            'name': 'Active EIMS Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', active_invoices.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }

    def action_bulk_cancel_eims(self):
        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        """
        Refactored to handle batch cancellation, individual logging,
        and individual email notifications for each invoice.
        """
        if not self:
            raise UserError("No invoices selected.")

        valid_invoices = self.filtered(lambda r: r.eims_irn)
        if not valid_invoices:
            raise UserError("Selected invoices must have an IRN to be cancelled.")

        # 1. Prepare batch items
        items_to_cancel = []
        for invoice in valid_invoices:
            items_to_cancel.append({
                "Irn": invoice.eims_irn,
                "ReasonCode": "1",
                "Remark": "Bulk Cancellation via Odoo",
            })

        try:
            # 2. Setup Secure Connection
            token, _ = self.env['eims.auth'].get_eims_token()
            param_obj = self.env['ir.config_parameter'].sudo()
            url = param_obj.get_param('eims.api_bulk.cancel_url',
                                      default='https://core.mor.gov.et/v1/bulkCancel')

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # 3. Sign and Post
            signed_payload = sign_eims_request(items_to_cancel)
            response = http.post(url, json=signed_payload, headers=headers, timeout=(5, 60))
            data = response.json()

            # 4. Handle Success Response
            if response.status_code == 200 and data.get("statusCode") == 200:
                results = data.get("body", [])

                for res_item in results:
                    # Isolate the specific singleton record
                    target_inv = valid_invoices.filtered(lambda i: i.eims_irn == res_item.get('Irn'))

                    if target_inv:
                        # Fix: Ensure we are working with one record (ID 500 then 479)
                        inv = target_inv[0]

                        # Update Invoice State
                        inv.write({
                            'eims_status': 'cancelled',
                            'eims_cancelled': True,
                            'eims_cancel_date': fields.Datetime.now(),
                            'eims_cancel_message': res_item.get('Remark', 'Bulk Cancelled'),
                        })

                        # Create Individual Log Entry
                        self.env["eims.cancel.log"].create({
                            "move_id": inv.id,
                            "partner_id": inv.partner_id.id,
                            "eims_irn": inv.eims_irn,
                            "reason_code": res_item.get("ReasonCode", "1"),
                            "remark": res_item.get("Remark", "Bulk Cancellation"),
                            "status": "success",
                            "cancellation_date": fields.Datetime.now(),
                            "eims_response": json.dumps(res_item, indent=2),
                            "eims_cancelled": True,
                            "eims_cancel_date": fields.Datetime.now(),
                        })

                        # --- INDIVIDUAL EMAIL LOGIC (Inside Success Loop) ---
                        try:
                            inv._send_eims_cancelled_email()
                            inv.message_post(body="✅ EIMS Cancellation email sent to student.")
                        except Exception as email_err:
                            inv.message_post(body=f"⚠ Cancellation email failed: {email_err}")

                        inv.message_post(body=f"✅ EIMS Bulk Cancelled. MoR ID: {res_item.get('id')}")

            else:
                # Handle Batch Failure
                for inv in valid_invoices:
                    self.env["eims.cancel.log"].create({
                        "move_id": inv.id,
                        "status": "failed",
                        "eims_response": json.dumps(data, indent=2),
                    })
                raise UserError(f"EIMS API Error: {data.get('message', 'SCHEMA_ERROR')}")

        except Exception as e:
            _logger.error(f"EIMS Bulk Cancel Crash: {str(e)}")
            raise UserError(f"System Error: {str(e)}")

        return self.action_view_sent_eims_invoices()

    # def action_bulk_cancel_eims(self):
    #     """Bulk cancel invoices in EIMS system"""
    #     self.ensure_one()

    # def action_send_bulk_to_eims(self):
    #     """Send a bulk of invoices to EIMS system"""
    #     self.ensure_one()

    def action_cancel_eims(self, reason_code="1"):
        # Get the smart session
        http = self.env['eims.auth'].get_eims_http_session()
        """Cancel a verified invoice in EIMS system, log it, and send cancellation email."""
        self.ensure_one()

        # Already cancelled
        if self.eims_status == 'cancelled':
            self.message_post(body="⚠️ Invoice already CANCELLED in EIMS. Skipped.")
            return

        if not self.eims_irn:
            raise UserError("❌ This invoice has no IRN and cannot be cancelled in EIMS.")

        try:
            # Get EIMS token
            token, _ = self.env['eims.auth'].get_eims_token()
            param_obj = self.env['ir.config_parameter'].sudo()
            url = param_obj.get_param('eims.api_single.cancel_url',
                                      default='https://core.mor.gov.et/v1/cancel')
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "Irn": self.eims_irn,
                "ReasonCode": reason_code,  # Use the passed reason code
                "Remark": "",
            }

            # Send cancellation request
            # ⃣ SIGN request (service layer)
            signed_payload = sign_eims_request(payload)
            response = http.post(url, json=signed_payload, headers=headers, timeout=(5, 30))
            data = response.json()

            if data.get("statusCode") == 200:
                cancel_date = data["body"].get("cancellationDate", "")
                self.eims_cancelled = True
                self.eims_cancel_date = fields.Datetime.now()
                self.eims_status = "cancelled"
                self.eims_cancel_message = data["body"].get("message", "No response message from EIMS.")

                # Post basic chatter message
                self.message_post(body=(
                    f"✅ EIMS Invoice Cancelled Successfully<br/>"
                    f"<b>Cancellation Date:</b> {cancel_date}"
                ))
                try:
                    self._send_eims_cancelled_email()
                except Exception as email_err:
                    self.message_post(body=f"⚠ Cancellation email failed: {email_err}")

                # Log cancellation
                self.env["eims.cancel.log"].create({
                    "move_id": self.id,
                    "partner_id": self.partner_id.id,
                    "eims_irn": self.eims_irn,
                    "reason_code": payload["ReasonCode"],
                    "remark": payload["Remark"],
                    "status": "success",
                    "cancellation_date": cancel_date,
                    "eims_response": json.dumps(data, indent=2),
                    "eims_cancelled": True,
                    "eims_cancel_date": fields.Datetime.now(),
                    "eims_cancel_message": self.eims_cancel_message,
                })


            else:
                # Log failed cancellation
                self.env["eims.cancel.log"].create({
                    "move_id": self.id,
                    "partner_id": self.partner_id.id,
                    "eims_irn": self.eims_irn,
                    "reason_code": payload["ReasonCode"],
                    "remark": payload["Remark"],
                    "status": "failed",
                    "eims_response": json.dumps(data, indent=2),
                })
                self.message_post(body=f"❌ EIMS Cancellation Failed: {data.get('message')}")



        except Exception as e:
            self.env["eims.cancel.log"].create({
                "move_id": self.id,
                "partner_id": self.partner_id.id,
                "eims_irn": self.eims_irn,
                "status": "failed",
                "eims_response": str(e),
            })
            self.message_post(body=f"⚠️ Cancellation Error: {str(e)}")

    @api.depends('invoice_date', 'eims_irn')
    def action_view_expired_eims_invoices(self):
        """Show invoices missing IRN and older than 72 hours."""
        limit_time = fields.Datetime.now() - timedelta(hours=72)

        return {
            'name': 'Expired EIMS Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('eims_irn', '=', False),
                ('invoice_date', '<', limit_time),
            ],
            'context': {'default_move_type': 'out_invoice'},
        }

    def _get_transaction_type(self, partner):
        # partner IS a res.partner already
        partner = partner.commercial_partner_id

        # Get company_type, default to 'person' if not set (Odoo's default for contacts)
        company_type = partner.company_type if partner.company_type else 'person'

        if company_type == "company":
            return "B2B"
        elif company_type in ["individual", "person"]:
            # Handle both 'individual' and 'person' (Odoo uses 'person' by default)
            return "B2C"
        else:
            raise UserError(
                f"❌ Customer '{partner.name}' has invalid Company Type: '{company_type}'.\n\n"
                f"Please set the customer type to either:\n"
                f"• Company (for B2B transactions requiring TIN)\n"
                f"• Individual (for B2C transactions without TIN)\n\n"
                f"You can edit this in Contacts → {partner.name} → Company Type field."
            )

    def get_tax_code(self, tax):
        name = (tax.description or tax.name or "").upper()

        if "15%" in name:
            return "VAT15"
        if "0%" in name:
            return "VAT0"
        if "EX" in name:  # catches 0%EXEPT, 0%EXEMPT, EXEMPT, etc.
            return "VATEX"

        # fallback
        return "VAT0"

    # prepare payload for single invoice

    from decimal import Decimal, ROUND_HALF_UP

    def prepare_eims_payload_single(self):
        self.ensure_one()
        company = self.env.company
        partner = self.partner_id

        # ----------------------------
        # Generate sequence number
        # ----------------------------
        sequence_number = int(self.env['ir.sequence'].next_by_code('eims.invoice.counter') or 0)
        self.eims_document_number = sequence_number
        self.eims_invoice_counter = sequence_number

        # ----------------------------
        # Determine transaction type once
        # ----------------------------
        transaction_type = self._get_transaction_type(partner)

        if transaction_type in ["B2C", "G2C"]:
            buyer_tin = None
            buyer_vat = None
        else:
            buyer_tin = partner.eims_tin
            buyer_vat = partner.eims_vat_number

        # ----------------------------
        # Initialize totals
        # ----------------------------
        item_list = []
        total_discount = Decimal('0.00')
        total_vat = Decimal('0.00')
        total_wh = Decimal('0.00')
        total_value = Decimal('0.00')
        total_excise = Decimal('0.00')

        # ----------------------------
        # LOOP over invoice lines
        # ----------------------------
        for idx, line in enumerate(self.invoice_line_ids, start=1):
            pre_tax = Decimal(str(line.price_subtotal))  # already after discount

            # Excise calculation including discount
            excise_value = Decimal('0.00')
            if line.x_excise_rate:
                line_total_before_tax = (Decimal(str(line.price_unit)) * Decimal(str(line.quantity)) *
                                         (Decimal('1.0') - Decimal(str(line.discount or 0)) / Decimal('100')))
                excise_value = (line_total_before_tax * Decimal(str(line.x_excise_rate)) / Decimal('100')).quantize(
                    Decimal('0.01'), ROUND_HALF_UP)

            # VAT calculation
            vat_rate = Decimal('0.00')
            if line.tax_ids:
                vat_rate = Decimal(str(line.tax_ids[0].amount)) / Decimal('100')

            # VAT amount = ((PreTaxValue + ExciseTaxValue) * VAT rate) + ExciseTaxValue
            vat_amount = ((pre_tax + excise_value) * vat_rate + excise_value).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Withholding
            wh_amount = Decimal('0.00')
            if line.withholding_eims:
                wh_amount = (pre_tax * Decimal('0.03')).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Determine EIMS tax code
            tax_code = "VAT0"
            if line.tax_ids:
                tax_code = self.get_tax_code(line.tax_ids[0])

            # Line discount
            line_discount = (Decimal(str(line.price_unit)) * Decimal(str(line.quantity)) * Decimal(
                str(line.discount)) / Decimal('100')).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Total line including VAT and Excise
            total_line = (pre_tax + vat_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Aggregate totals
            total_discount += line_discount
            total_vat += vat_amount
            total_wh += wh_amount
            total_excise += excise_value
            total_value += total_line

            # Append item
            item_list.append({
                "Discount": float(line_discount),
                "NatureOfSupplies": "goods",
                "ItemCode": line.product_id.default_code or str(line.id),
                "ProductDescription": line.name,
                "PreTaxValue": float(pre_tax),
                "Quantity": line.quantity,
                "LineNumber": idx,
                "TaxAmount": float(vat_amount),
                "TaxCode": tax_code,
                "TotalLineAmount": float(total_line),
                "Unit": "PCS",
                "UnitPrice": float(line.price_unit),
                "HarmonizationCode": line.x_harmonization_code or "0000",
                "ExciseTaxValue": float(excise_value),
            })

        # ----------------------------
        # FINAL PAYLOAD
        # ----------------------------
        return {
            "BuyerDetails": {
                "LegalName": partner.name,
                "Tin": buyer_tin,
                "IdType": "KID",
                "IdNumber": partner.eims_id_number,
                "VatNumber": buyer_vat,
                "Phone": partner.phone or "",
                "Email": partner.email or "",
                "City": partner.eims_buyers_city_code or "0",
                "Region": partner.eims_region or "01",
                "Wereda": partner.eims_wereda or "01",
            },
            "DocumentDetails": {
                "DocumentNumber": sequence_number,
                "Date": self.invoice_date.strftime('%d-%m-%YT%H:%M:%S'),
                "Type": "INV",
            },
            "ItemList": item_list,
            "PaymentDetails": {
                "Mode": "CASH",
                "PaymentTerm": "IMMEDIATE",
            },
            "SellerDetails": {
                "LegalName": company.name,
                "Tin": company.eims_tin,
                "VatNumber": company.eims_vat_number,
                "Email": company.email,
                "Phone": company.phone,
                "City": company.eims_seller_city_code,
                "Region": company.eims_region,
                "Wereda": company.eims_wereda,
            },
            "SourceSystem": {
                "CashierName": "AAA",
                "InvoiceCounter": sequence_number,
                "SalesPersonName": "AAA",
                "SystemNumber": company.eims_system_number,
                "SystemType": "POS",
            },
            "ReferenceDetails": {
                "PreviousIrn": ""
            },
            "TransactionType": transaction_type,
            "ValueDetails": {
                "Discount": float(total_discount),
                "TaxValue": float(total_vat),
                "IncomeWithholdValue": float(total_wh),
                "TotalValue": float(total_value),
                "ExciseValue": float(total_excise),
                "TransactionWithholdValue": 0.0,
                "InvoiceCurrency": self.currency_id.name,
            },
            "Version": "1",

        }

    def prepare_eims_payload_credit_memo(self):
        """Prepare EIMS payload for a credit memo (CRE) linked to an original invoice"""
        self.ensure_one()
        company = self.env.company
        partner = self.partner_id

        if not self.reversed_entry_id or not self.reversed_entry_id.eims_irn:
            raise UserError("❌ Original invoice is not registered in EIMS. Cannot send Credit Memo.")

        # Generate sequence number for the CRE

        sequence_number = int(self.env['ir.sequence'].next_by_code('eims.invoice.counter') or 0)
        self.eims_document_number = sequence_number
        self.eims_invoice_counter = sequence_number

        # Initialize totals
        item_list = []
        total_discount = Decimal('0.00')
        total_vat = Decimal('0.00')
        total_wh = Decimal('0.00')
        total_value = Decimal('0.00')
        total_excise = Decimal('0.00')

        # Loop over invoice lines
        for idx, line in enumerate(self.invoice_line_ids, start=1):
            pre_tax = Decimal(str(line.price_subtotal))

            # Excise
            excise_value = Decimal('0.00')
            if line.x_excise_rate:
                line_total_before_tax = (Decimal(str(line.price_unit)) * Decimal(str(line.quantity)) *
                                         (Decimal('1.0') - Decimal(str(line.discount or 0)) / Decimal('100')))
                excise_value = (line_total_before_tax * Decimal(str(line.x_excise_rate)) / Decimal('100')).quantize(
                    Decimal('0.01'), ROUND_HALF_UP)

            # VAT
            vat_rate = Decimal(str(line.tax_ids[0].amount)) / Decimal('100') if line.tax_ids else Decimal('0.00')
            vat_amount = ((pre_tax + excise_value) * vat_rate + excise_value).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Withholding
            wh_amount = (pre_tax * Decimal('0.03')).quantize(Decimal('0.01'),
                                                             ROUND_HALF_UP) if line.withholding_eims else Decimal(
                '0.00')

            # Line discount
            line_discount = (Decimal(str(line.price_unit)) * Decimal(str(line.quantity)) * Decimal(
                str(line.discount)) / Decimal('100')).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Total line including VAT & Excise
            total_line = (pre_tax + vat_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)

            # Append item
            item_list.append({
                "Discount": float(line_discount),
                "NatureOfSupplies": "goods",
                "ItemCode": line.product_id.default_code or str(line.id),
                "ProductDescription": line.name,
                "PreTaxValue": float(pre_tax),
                "Quantity": line.quantity,
                "LineNumber": idx,
                "TaxAmount": float(vat_amount),
                "TaxCode": "VAT15" if line.tax_ids else "VAT0",
                "TotalLineAmount": float(total_line),
                "Unit": "PCS",
                "UnitPrice": float(line.price_unit),
                "ExciseTaxValue": float(excise_value),
            })

            total_discount += line_discount
            total_vat += vat_amount
            total_wh += wh_amount
            total_value += total_line
            total_excise += excise_value

        # Final payload
        return {
            "BuyerDetails": {
                "LegalName": partner.name,
                "Tin": partner.eims_tin,
                "IdType": "KID",
                "IdNumber": partner.eims_id_number,
                "VatNumber": partner.eims_vat_number,
                "Phone": partner.phone or "",
                "Email": partner.email or "",
                "City": partner.eims_buyers_city_code or "0",
                "Region": partner.eims_region or "01",
                "Wereda": partner.eims_wereda or "01",
            },
            "DocumentDetails": {
                "DocumentNumber": sequence_number,
                "Date": self.invoice_date.strftime('%d-%m-%YT%H:%M:%S'),
                "Type": self._get_eims_doc_type(),
                "Reason": self.ref or "Credit Memo Adjustment",
            },
            "ItemList": item_list,
            "PaymentDetails": {
                "Mode": "CASH",
                "PaymentTerm": "IMMEDIATE",
            },
            "ReferenceDetails": {
                "RelatedDocument": self.reversed_entry_id.eims_irn,
                "PreviousIrn": ""
            },
            "SellerDetails": {
                "LegalName": company.name,
                "Tin": company.eims_tin,
                "VatNumber": company.eims_vat_number,
                "Email": company.email,
                "Phone": company.phone,
                "City": company.eims_seller_city_code,
                "Region": company.eims_region,
                "Wereda": company.eims_wereda,
            },
            "SourceSystem": {
                "CashierName": "AAA",
                "InvoiceCounter": sequence_number,
                "SalesPersonName": "AAA",
                "SystemNumber": company.eims_system_number,
                "SystemType": "POS",
            },
            "TransactionType": "B2B",
            "ValueDetails": {
                "Discount": float(total_discount),
                "TaxValue": float(total_vat),
                "IncomeWithholdValue": float(total_wh),
                "TotalValue": float(total_value),
                "ExciseValue": float(total_excise),
                "TransactionWithholdValue": 0.0,
                "InvoiceCurrency": self.currency_id.name,
            },
            "Version": "1",
        }




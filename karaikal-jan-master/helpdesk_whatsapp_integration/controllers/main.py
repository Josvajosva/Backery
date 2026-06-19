from odoo import http,_
from odoo.http import request, Response
import json
import requests
import logging
_logger = logging.getLogger(__name__)

class HelpdeskTicketController(http.Controller):

    @http.route('/api/v1/ticket_status', type='json', auth='public', methods=['GET'], csrf=False)
    def get_ticket_status(self, **kwargs):
        # JSON routes get parameters from 'params' in the request body, not kwargs for GET
        # Note: Odoo type='json' usually expects POST with a JSON-RPC body
        params = request.params if request.params else kwargs
        
        token = request.httprequest.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        else:
            token = params.get('api_token')

        if not token:
            return {'error': 'Missing API token', 'status': 401}

        # Validate token - check if your key actually uses this scope
        user_id = request.env['res.users.apikeys'].sudo()._check_credentials(scope='odoo.restapi', key=token)
        if not user_id:
            return {'error': 'Invalid token', 'status': 403}

        ticket_id = params.get('ticket_id')
        if ticket_id:
            ticket = request.env['helpdesk.ticket'].sudo().search([('ticket_ref', 'ilike', ticket_id)], limit=1)
            if not ticket:
                return {'status': 'error', 'message': 'Ticket not found'}

            return {
                'status': ticket.stage_id.name,
                'ticket_id': ticket.ticket_ref,
                'last_updated': str(ticket.write_date),
                'assigned_to': ticket.user_id.name if ticket.user_id else False,
                'remarks': ticket.ticket_response,
            }
        return {'error': 'Missing ticket_id'}



    @http.route('/api/v1/create_ticket', type='json', auth='public', methods=['POST'], csrf=False)
    def create_ticket_webhook(self, **post_data):
        """
        Receives a JSON payload via POST request and creates a Helpdesk Ticket.
        """
        
        # Odoo automatically parses the JSON body for 'type="json"' routes
        # If using type='http', you'd parse request.httprequest.data manually.

        try:
            _logger.info('API Create Ticket')
            _logger.info(post_data)
            token = request.httprequest.headers.get('Authorization')
            if token and token.startswith('Bearer '):
                token = token[7:]
            elif not token:
                token = post_data.get('api_token')

            if not token:
                return {'success': False, 'error': 'Missing API token.'}

            # Validate API token
            user = request.env['res.users.apikeys']._check_credentials(scope='odoo.restapi', key=token)
            if not user:
                return {'success': False, 'error': 'Invalid or expired API token.'}
            # Extract data from the incoming request payload
            complaint = post_data.get('complaint', 'Default API Ticket Subject')
            employee_created = post_data.get('employee_created_ticket', False)
            description = post_data.get('details', ' ')
            complaint_type = post_data.get('type', False)
            customer_mobile = post_data.get('mobile', False)
            customer_name = post_data.get('name', False)
            store_location = post_data.get('store_location', False)
            store_identifier = post_data.get('store_identifier', False)
            equipment_name = post_data.get('equipment_name', False)
            priority = post_data.get('priority', False)
            complaint_department = post_data.get('complaint_department', False)
            
            image_url = post_data.get('image_url', False)
            affected_areas = post_data.get('affected_areas', False)
            quality_issue_type = post_data.get('quality_issue_type', False)
            quality_issue_product = post_data.get('quality_issue_product', False)
            system_name = post_data.get('system_name', False)
            employee_details = post_data.get('employee_details', False)
            grievance_category = post_data.get('grievance_category', False)
            product_enquiry = post_data.get('product_enquiry', False)
            required_qty = post_data.get('required_qty', False)
            expected_delivery = post_data.get('expected_delivery', False)
            complaint_regarding = post_data.get('complaint_regarding', False)
            critical_level = post_data.get('critical_level', False)
            material_category = post_data.get('material_category', False)
            shortage_material = post_data.get('shortage_material', False)

            complaint_name  = str(complaint) if complaint else str(complaint_type)
            whatsapp_head = 'Employee' if employee_created else 'Customer'
            # Find the target helpdesk team ID (e.g., Team 1)
            # You might want to dynamically search for a team here
            #team_id = 1 

            # Access the 'helpdesk.ticket' model via the request environment (request.env)
            # Call the 'create' method directly with a dictionary of values
            partner_obj = request.env['res.partner'].sudo().search([('mobile','=',customer_mobile)])
            department_obj = request.env['hr.department'].sudo().search([('dp_code','=',complaint_department)], limit=1)
            type_obj = request.env['helpdesk.ticket.type'].sudo().search([('whatsapp_option','=',complaint_type),('whatsapp_category','=',whatsapp_head)], limit=1)
            equipment_obj = request.env['maintenance.equipment'].sudo().search([('serial_no','=',equipment_name)])
            message = _("Ticket type '%s' and team %s", type_obj, type_obj.team_id)
            _logger.info(message)
            if not partner_obj:
                partner_obj = request.env['res.partner'].sudo().create({
                    'name': customer_name,
                    'mobile': customer_mobile,
                })
            if partner_obj:
                new_ticket = request.env['helpdesk.ticket'].sudo().create({
                    'name': complaint_name,
                    'description': description,
                    #'email': customer_email,
                    'partner_id': partner_obj[0].id,
                    'type_id': type_obj[0].id if type_obj else False,
                    'team_id': type_obj[0].team_id.id if (type_obj and type_obj.team_id) else False,
                    'partner_name': customer_name,
                    'partner_mobile': customer_mobile,
                    #'team_id': team_id,
                    'store_location': store_location,
                    'store_identifier': store_identifier,
                    'equipment_id': equipment_obj[0].id if (equipment_obj and equipment_name) else False,
                    'equipment_name': equipment_name,
                    #'equipment_spec': '',
                    'employee_created': employee_created,
                    'priority': priority,
                    'department_id': department_obj[0].id if department_obj else False,

                    'image_url': image_url,
                    'affected_areas': affected_areas,
                    'quality_issue_type': quality_issue_type,
                    'quality_issue_product': quality_issue_product,
                    'system_name': system_name,
                    'employee_details': employee_details,
                    'grievance_category': grievance_category,
                    'product_enquiry': product_enquiry,
                    'required_qty': required_qty,
                    'expected_delivery': expected_delivery,
                    'complaint_regarding': complaint_regarding,
                    'critical_level': critical_level,
                    'material_category': material_category,
                    'shortage_material': shortage_material,

                    # Add other fields as needed (e.g., 'priority', 'tag_ids', etc.)
                })

                # Return a JSON response
                return {
                    'status': 'success',
                    'ticket_id': new_ticket.ticket_ref,
                    'message': f'Ticket {new_ticket.ticket_ref} created successfully.'
                }
            else:
                return {
                    'status': 'error',
                    'message': f"{customer_mobile} - this mobile no is not available in customer master"
                }
        except Exception as e:
            # Handle potential errors during creation (e.g., missing required fields)
            return {
                'status': 'error',
                'message': str(e),
                'traceback': 'See server logs for details'
            }

class HelpdeskTicket_WA:

    def api_ticket_reply_wa(self, ticket, message, **kw):
        try:
            if ticket:
                data = {
                    "to": ticket.partner_mobile,
                    "recipient_type": "individual",
                    "type": "template",
                    "template": {
                        "language": {
                            "policy": "deterministic",
                            "code": "en"
                        },
                        "name": "ticket_closure",
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {
                                        "text": str(ticket.ticket_ref)+'\n'+str(message),
                                        "type": "text"
                                    }
                                ]
                            }
                        ]
                    }
                }

                url = f"https://crm.saaselixir.com/api/meta/v19.0/362673426918766/messages"
                headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer 6AqcHq33YekUDknb2JcR1VU5ERVJTQ09SRQrazDMtMbPlVOhrVs0REFTSAoXlN1WKH3PaVNq8C3lREFTSA4BzX61Ok3kAzeyyOlSWR3Eu6FF8YwMjp2IZCvUZQUEDMH2b02KcmmsVU5ERVJTQ09SRQrp2cqLRP8einREFTSAVU5ERVJTQ09SRQ1icQC8epBUwIzuBedeqZK9Yj1y8N7LXqdOEMxzUaVU5ERVJTQ09SRQjeREFTSAZRtHt3baknV1pFFldYVU5ERVJTQ09SRQiJgbQhOFzct1lp6a82Ny7FwCbbwvVU5ERVJTQ09SRQ4gc2lxoREFTSAkA'}
                _logger.info('API URL: %s', url)
                _logger.info('Payload: %s', data)
                response = requests.post(url, json=data, headers=headers)
                _logger.info('API Response: %s', response.text)
                response_data = response.json()
                _logger.info("Sent successfully")
                return response_data
            else:
                _logger.error("Failed")
                return {'error': "Failed"}
        except json.JSONDecodeError:
            _logger.error("Invalid JSON format in API response")
            return {'error': "Invalid JSON format"}
        except Exception as e:
            _logger.error(f"Internal Server Error: {str(e)}")

            return {'error': f"Internal Server Error: {str(e)}"}



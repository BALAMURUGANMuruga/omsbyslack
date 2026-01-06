import os
from flask import Flask, request,Response, jsonify
import requests
import xmltodict
import copy
from datetime import datetime
import random
from flask_cors import CORS
import slack


app = Flask(__name__)
CORS(app)

# =========================
# 1. Configuration
# =========================
URL = "http://localhost:9080/smcfs/interop/InteropHttpServlet"
USER = "admin"
PASSWORD = "password"
USER_NAME = "balamurugan"

# =========================
# 2. Templates
# =========================
ORDER_JSON_TEMPLATE = {
    "Order": {
        "@OrderNo": "",
        "@DocumentType": "0001",
        "@SellerOrganizationCode": "Matrix-R",
        "@EnterpriseCode": "Matrix-R",
        "@EntryType": "Web",
        "@PaymentStatus": "AUTHORIZED",
        "@CustomerEMailID": "july20@test.com",
        "@ValidateItem": "Y",
        "@OrderType": "SDP",
        "@NotificationType": "SUBSTITUTION",
        "Extn": {"@ExtnWCSOrderNo": "123456789"},
        "PriceInfo": {"@Currency": "USD"},
        "PersonInfoBillTo": {
            "@Title": "Mr",
            "@FirstName": "BEXLEY",
            "@LastName": "HEATH",
            "@AddressLine1": "55 The Broadway",
            "@AddressLine2": "BEXLEYHEATH",
            "@City": "Brockton",
            "@Country": "US",
            "@EMailID": "BEXLEY.HEATH@gmail.com",
            "@ZipCode": "02302",
            "@DayPhone": ""
        },
        "OrderLines": {
            "OrderLine": [
                {
                    "@OrderedQty": "5",
                    "@SubLineNo": "1",
                    "@LineType": "GM",
                    "@DeliveryMethod": "SHP",
                    "@PrimeLineNo": "1",
                    "@ShipNode": "Mtrx_Store_1",
                    "Item": {
                        "@ItemID": "100001",
                        "@UnitOfMeasure": "EACH",
                        "Extn": {"@ExtnItemMRP": "5.00"}
                    },
                    "PersonInfoShipTo": {
                        "@Title": "Mr",
                        "@AddressLine1": "55 The Broadway",
                        "@AddressLine2": "BEXLEYHEATH",
                        "@City": "Brockton",
                        "@Country": "US",
                        "@FirstName": "Sakthi",
                        "@EMailID": "sakthi@gmail.com",
                        "@LastName": "rajeswari",
                        "@ZipCode": "02302"
                    },
                    "LinePriceInfo": {"@IsPriceLocked": "Y", "@UnitPrice": "5"},
                }
            ]
        }
    }
}

OUTPUT_TEMPLATE = {
    "Order": {
        "@OrderHeaderKey": "",
        "OrderHoldTypes": {"OrderHoldType": {"@HoldType": "", "@Status": "", "@ReasonText": ""}}
    }
}

ORDER_DETAILS_TEMPLATE = {
    "Order": {
        "@OrderHeaderKey": "",
        "OrderLines": {
            "OrderLine": {
                "@PrimeLineNo": "",
                "@SubLineNo": "",
                "@OrderLineKey": "",
                "@OrderedQty": "",
                "Item": {"@ItemID": ""}
            }
        },
        "OrderStatuses": {
            "OrderStatus": {
                "@OrderLineKey": "",
                "@OrderReleaseKey": ""
            }
        }
    }
}

ORDER_STATUS_LIST = ["CREATED", "SCHEDULED", "RELEASE", "INCLUDED IN SHIPMENT", "SHIP"]

# =========================
# 3. Helper Functions
# =========================
def post_interop(api_name, xml_payload, template=None):
    data = {
        "YFSEnvironment.progId": "SterlingHttpTester",
        "InteropApiName": api_name,
        "IsFlow": "N",
        "ServiceName": "",
        "ApiName": api_name,
        "YFSEnvironment.userId": USER,
        "YFSEnvironment.password": PASSWORD,
        "InteropApiData": xml_payload
    }
    if template:
        data["TemplateData"] = xmltodict.unparse(template, pretty=True)
    response = requests.post(URL, data=data, timeout=60)
    return response


def generate_order_no():
    now = datetime.now()
    rand = random.randint(1, 99)
    return f"B{now.strftime('%d%m%y%H%M')}{rand:02d}"


def ensure_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def process_single_order(order_template, target_status_idx, session):
    logs = []
    shipment_key = ""
    seller_org_code = ""
    shipment_no = ""
    order_header_key = ""

    # Step 1: Create order
    order_json = copy.deepcopy(order_template)
    order_no = generate_order_no()
    order_json["Order"]["@OrderNo"] = order_no

    xml_data = xmltodict.unparse(order_json, pretty=True)
    resp = post_interop("createOrder", xml_data, OUTPUT_TEMPLATE)
    resp_dict = xmltodict.parse(resp.text)
    order_header_key = resp_dict.get("Order", {}).get("@OrderHeaderKey", "")

     # Only after creation, append the order link
    order_link_obj = {
        "message": f"Open Order {order_no} in call center",
        "orderLink": f"https://localhost:6443/call-center/order-details?orderNo={order_no}&orderHeaderKey={order_header_key}&enterprise=Matrix-R&title={order_no}&prev=7072&session={session}&featureId=cc-order-details&uniqueId=9593&bcRoot=7072"
    }
    logs.append(order_link_obj)

    logs.append(f"✅ Created Order: {order_no}")

    # Step 2: Release Holds immediately after creation
    order_hold_type = resp_dict.get("Order", {}).get("OrderHoldTypes", {}).get("OrderHoldType", None)
    if order_hold_type:
        hold_list = order_hold_type if isinstance(order_hold_type, list) else [order_hold_type]
        for hold in hold_list:
            hold["@Status"] = "1300"  # released
        hold_xml = {
            "Order": {
                "@OrderHeaderKey": order_header_key,
                "OrderHoldTypes": {"OrderHoldType": hold_list}
            }
        }
        form_hold = {
            "YFSEnvironment.progId": "SterlingHttpTester",
            "InteropApiName": "changeOrder",
            "IsFlow": "N",
            "ServiceName": "",
            "ApiName": "changeOrder",
            "YFSEnvironment.userId": USER,
            "YFSEnvironment.password": PASSWORD,
            "InteropApiData": xmltodict.unparse(hold_xml, pretty=True)
        }
        resp_hold = requests.post(URL, data=form_hold)
        logs.append(f"🛠️ Holds released for Order {order_no}")

    # Step 3: Move through remaining statuses
    for status in ORDER_STATUS_LIST[1:target_status_idx]:
        api_name = None
        xml_data = None

        if status == "SCHEDULED":
            api_name = "scheduleOrder"
            xml_data = xmltodict.unparse(
                {"ScheduleOrder": {"@OrderHeaderKey": order_header_key}}, pretty=True
            )

        elif status == "RELEASE":
            api_name = "releaseOrder"
            xml_data = xmltodict.unparse(
                {"ReleaseOrder": {
                    "@OrderHeaderKey": order_header_key,
                    "@IgnoreTransactionDependencies": "Y",
                    "@IgnoreReleaseDate": "Y"
                }}, pretty=True
            )

        elif status == "INCLUDED IN SHIPMENT":
            api_name = "createShipment"
            # Fetch order details
            order_details_xml = xmltodict.unparse({"Order": {"@OrderHeaderKey": order_header_key}}, pretty=True)
            form_status = {
                "YFSEnvironment.progId": "SterlingHttpTester",
                "InteropApiName": "getOrderDetails",
                "IsFlow": "N",
                "ServiceName": "",
                "ApiName": "getOrderDetails",
                "YFSEnvironment.userId": USER,
                "YFSEnvironment.password": PASSWORD,
                "InteropApiData": order_details_xml,
                "TemplateData": xmltodict.unparse(ORDER_DETAILS_TEMPLATE, pretty=True)
            }
            resp_status = requests.post(URL, data=form_status)
            resp_dict = xmltodict.parse(resp_status.text)

            order_lines = ensure_list(resp_dict.get("Order", {}).get("OrderLines", {}).get("OrderLine", []))
            order_statuses = ensure_list(resp_dict.get("Order", {}).get("OrderStatuses", {}).get("OrderStatus", []))

            shipment_lines = []
            for line in order_lines:
                item_id = line.get("Item", {}).get("@ItemID", "")
                order_line_key = line.get("@OrderLineKey", "")
                prime_line_no = line.get("@PrimeLineNo", "")
                sub_line_no = line.get("@SubLineNo", "")
                qty = line.get("@OrderedQty", "0")

                for status_entry in order_statuses:
                    if status_entry.get("@OrderLineKey", "") == order_line_key:
                        release_key = status_entry.get("@OrderReleaseKey", "")
                        shipment_lines.append({
                            "@OrderReleaseKey": release_key,
                            "@ItemID": item_id,
                            "@Quantity": qty,
                            "@PrimeLineNo": prime_line_no,
                            "@SubLineNo": sub_line_no
                        })
                        break

            shipment_dict = {"Shipment": {"@OrderHeaderKey": order_header_key, "ShipmentLines": {"ShipmentLine": shipment_lines}}}
            xml_data = xmltodict.unparse(shipment_dict, pretty=True)

        elif status == "SHIP":
            api_name = "confirmShipment"
            xml_data = xmltodict.unparse(
                {"Shipment": {
                    "@ShipmentKey": shipment_key,
                    "@SellerOrganizationCode": seller_org_code,
                    "@ShipmentNo": shipment_no
                }},
                pretty=True
            )

        if not api_name:
            continue

        resp = post_interop(api_name, xml_data, OUTPUT_TEMPLATE)
        resp_dict = xmltodict.parse(resp.text)

        if "Errors" in resp_dict:
            logs.append(f"❌ Error moving to {status}")
        else:
           
            logs.append(f"✅ Order {order_no} moved to {status} successfully")
        
    return logs

# =========================
# 4. Chatbot Conversation Logic
# =========================
user_state = {}

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = (data.get("message") or "").strip().lower()
    user_id = "default"

    if any(phrase in msg for phrase in ["create order", "start create", "can you create"]):
        user_state[user_id] = {"step": "ask_count"}
        return jsonify({"reply": "✅ How many orders do you want to create?"})

    if user_state.get(user_id, {}).get("step") == "ask_count":
        if msg.isdigit():
            user_state[user_id]["count"] = int(msg)
            user_state[user_id]["step"] = "ask_status"
            status_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(ORDER_STATUS_LIST)])

            return jsonify({
                "reply": f"📦 Great! Choose the order status:\n\n{status_text}"
            })
        else:
            return jsonify({"reply": "⚠️ Please enter a valid number."})

    if user_state.get(user_id, {}).get("step") == "ask_status":
        selected_status = None
        for i, status in enumerate(ORDER_STATUS_LIST, start=1):
            if msg == str(i) or msg in status.lower():
                selected_status = status
                target_idx = i
                break

        if not selected_status:
            # Format into Slack-friendly list
            status_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(ORDER_STATUS_LIST)])
            return jsonify({
                "reply": f"⚠️ Please select a valid status from the list:\n\n{status_text}"
            })

        # proceed with order creation
        count = user_state[user_id]["count"]
        user_state[user_id]["step"] = None
        logs = []

        for i in range(count):
            session_id = i + 1
            logs.extend(process_single_order(ORDER_JSON_TEMPLATE, target_idx, str(session_id)))

        return jsonify({"reply": logs})


    if msg in ["hi", "hello", "hey", "start"]:
        return jsonify({"reply": "👋 Hi! I can create and move orders. Type 'create order' to begin."})

    if msg == "help":
        return jsonify({"reply": "💡 Commands: create order, help, status"})

    return jsonify({"reply": "🤖 Sorry, I didn’t understand that. Try 'create order' or 'help'."})


# =========================
# 5. API: Status options endpoint
# =========================
@app.route('/status-options', methods=['GET'])
def get_status_options():
    return jsonify({"options": ORDER_STATUS_LIST[1:]})


@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(force=True)

    # 🔑 Slack URL verification
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        return Response(challenge, status=200, mimetype="text/plain")

    return slack.handle_event(request.json)

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "OMS by Slack is running 🚀", 200

# def main():
#     port = int(os.environ.get("PORT", 10000))
#     app.run(host="0.0.0.0", port=port)

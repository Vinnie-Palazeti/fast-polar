from fasthtml.common import *
from fasthtml.oauth import GoogleAppClient, OAuth
from starlette.responses import RedirectResponse
from user_storage import UserStorage
from polar_sdk import Polar
from polar_sdk.webhooks import validate_event, WebhookVerificationError
import polar_sdk
import time
import os

app, rt = fast_app(
    pico=False,
    live=True,
    hdrs=(
        Link(href="https://cdn.jsdelivr.net/npm/daisyui@5", rel="stylesheet", type='text/css'),
        Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4")
    )
)

oauth_client = GoogleAppClient(
    os.getenv("AUTH_CLIENT_ID"), 
    os.getenv("AUTH_CLIENT_SECRET"),
    redirect_uri=f'{os.getenv("NGROK_ENDPOINT")}/redirect',
)

class Auth(OAuth):
    def __init__(self, app, oauth_client, skip=None):
        super().__init__(app, oauth_client, skip=skip)
        self.user_storage = UserStorage()

    def get_auth(self, info, ident, session, state):
        email = info.email or ''
        if info.email_verified and email:
            user = self.user_storage.create_or_update_user(email=email, name=info.name or email.split('@')[0])
            session["user_id"]=user.id
            session["user_name"]=user.name
            session["user_email"]=user.email
            return RedirectResponse("/product", status_code=303)
        return RedirectResponse("/login", status_code=303)

oauth = Auth(
    app,
    oauth_client,
    skip=[
        "/",                   # landing page
        "/login",              # render sign-in page
        "/logout",             # destroy session
        "/redirect",           # Google callback
        "/webhook",            # Polar Webhook
        "/success"             # Polar Success
    ]
)

# this feels clunky
PORT=5001
os.environ['POLAR_SUCCESS_URL'] = f'{os.getenv("NGROK_ENDPOINT")}/success?checkout_id={{CHECKOUT_ID}}'

@rt("/static/{file_path:path}.{ext:static}")
def static(file_path: str, ext: str):
    return FileResponse(f"static/{file_path}.{ext}")

@rt('/')
async def get(auth, session):
    auth = session.get('auth')
    options = [
        A('Login', href='/login', cls='btn btn-primary btn-lg text-white') if not auth else None,
        A('Log Out', href='/logout', cls='btn btn-primary btn-lg text-white') if auth else None,
        A('Products', href='/product', cls='btn btn-primary btn-lg text-white') if auth else None,
    ]
    return Div(cls="min-h-screen flex items-center justify-center p-4")(
        Div(cls="w-full max-w-4xl mx-auto")(
            Div(cls="justify-center text-center mb-8")(
                H2(f"You are {'not' if not auth else ''} Authed!", cls="text-3xl font-bold text-primary mb-2"),
                Div(cls='flex flex-row gap-x-4 justify-center ')(*options)
            ),
        )
    )

@rt("/login")
async def login(req):
    return Div(cls="min-h-screen flex items-center justify-center")(
        Div(cls="max-w-md mx-auto")(
            Div(cls="text-center mb-4")(H2("Click to Auth", cls="text-3xl font-bold text-primary mb-2")),            
            Div(cls="card bg-base-100 shadow-2xl border border-base-300")(
                Div(cls="card-body text-center p-8")(A("Sign in with Google", href=oauth.login_link(req), cls="btn btn-primary btn-lg text-white"))
            )
        )
    )

@rt("/logout")
async def logout(session):
    return oauth.logout(session)

@rt('/create-checkout')
async def post(auth, session, product_id:str):
    if not all([auth, session.get('user_id'), session.get('user_email')]): # overkill
        return RedirectResponse("/login", status_code=303)
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        res = polar.checkouts.create(request={
            "products": [product_id],
            "success_url": os.environ.get("POLAR_SUCCESS_URL"),
            'external_customer_id': session.get('user_id'),
            'customer_email': session.get('user_email')
        })
    return Response("", headers={"HX-Redirect": res.url})

@rt('/success')
async def get(req, auth, session, checkout_id:str, customer_session_token:str=None):        
    return (
        Body(cls='relative overflow-hidden bg-gray-100 h-screen flex items-center justify-center')(
            Div(cls='z-10 text-center')(
                H1('Success!', cls='text-4xl font-bold text-green-600 mb-4'),
                P('Your purchase is complete! 🎉', cls='text-gray-700'),
                A("Visit Product Page", href='/product', cls="btn btn-primary text-white btn-lg mt-10")
            ),
        ) 
    )

@rt('/update-subscription')
async def post(user_id:str, subscription_id:str, product_id:str):
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        cust_session = polar.customer_sessions.create(request={"external_customer_id": user_id})
        res = polar.customer_portal.subscriptions.update(
            security=polar_sdk.CustomerPortalSubscriptionsUpdateSecurity(
            customer_session=cust_session.token), 
            id=subscription_id,
            customer_subscription_update={'product_id':product_id}
        )
        time.sleep(2) 
    return Response("", headers={"HX-Redirect": '/product'})   
    
@rt('/uncancel-subscription')
async def post(user_id:str, subscription_id:str,):
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        cust_session = polar.customer_sessions.create(request={"external_customer_id": user_id})
        print('session:', cust_session)
        res = polar.customer_portal.subscriptions.update(
            security=polar_sdk.CustomerPortalSubscriptionsUpdateSecurity(
            customer_session=cust_session.token), 
            id=subscription_id,
            customer_subscription_update={'cancel_at_period_end':False}
        ) 
        time.sleep(2)
    return Response("", headers={"HX-Redirect": '/product'})
    
@rt('/cancel-subscription')
async def post(user_id:str, subscription_id:str):
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        cust_session = polar.customer_sessions.create(request={"external_customer_id": user_id})
        res = polar.customer_portal.subscriptions.cancel(
            security=polar_sdk.CustomerPortalSubscriptionsCancelSecurity(
            customer_session=cust_session.token), 
            id=subscription_id
        )
        time.sleep(2)
    return Response("", headers={"HX-Redirect": '/product'})

### probably do not want this as an actual option for users
@rt('/revoke-subscription')
async def post(subscription_id:str,):
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        res = polar.subscriptions.revoke(id=subscription_id)
        time.sleep(2)
    return Response("", headers={"HX-Redirect": '/product'})   
        
@rt("/product")
async def get(auth, session):
    print('reload!')
    if not auth:
        return RedirectResponse("/login", status_code=303)
    
    ## session info
    session_cards = [
        Div(cls="card bg-base-100 shadow-xl")(
            Div(cls="card-body p-4")(
                H3(key, cls="card-title text-sm text-primary"),
                P(f"{session.get(key, 'N/A')}", cls="text-lg font-mono break-words")
            )
        ) for key in ['user_id','user_name','user_email','auth']
    ]
    
    ## get current products
    with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
        products = polar.products.list(organization_id=os.getenv("POLAR_ORG_ID"), page=1, limit=10)
    products = [(i.name, i.description, i.id, i.prices[0].price_amount)  # simplifying. prices list contains history of prices.. grabbing the first one
                for i in products.result.items]

    ## check customer state 
    try:
        with Polar(server="sandbox", access_token=os.getenv("POLAR_ACCESS_TOKEN")) as polar:
            customer = polar.customers.get_state_external(external_id=session.get('user_id'))
        session["polar_id"] = customer.id
        active_subscription = [i for i in customer.active_subscriptions if i.STATUS == 'active'][0] # there can only be 1 active subscription. not sure if this is the best method.
    except:
        session["polar_id"] = None
        active_subscription = {}

    ## product cards with options that change based on subscription status
    product_cards = [
        Div(cls="card bg-base-100 shadow-xl")(
            Div(cls="card-body p-4 flex flex-col")(
                H3(name, cls="card-title text-sm text-primary"),
                P(description, cls="text-base mb-2 break-words flex-grow"),
                Div(cls="flex justify-between items-center mb-3")(
                    P(f"${price_amount/100:.2f}", cls="text-lg font-bold text-success"),
                ),
                (
                    Button("Purchase", name='purchase', id='purchase-btn', hx_post=f"/create-checkout?product_id={product_id}", cls="btn btn-primary text-white btn-sm w-full") if not active_subscription else
                    Button("Uncancel", name='uncancel', id='uncancel-btn', hx_post=f"/uncancel-subscription", hx_vals=dict(subscription_id=active_subscription.id, user_id=session.get('user_id')), cls="btn btn-accent btn-sm text-white w-full") if (product_id == active_subscription.product_id) and (active_subscription.cancel_at_period_end == True) else
                    Button("Cancel", name='cancel', id='cancel-btn', hx_post=f"/cancel-subscription", hx_vals=dict(subscription_id=active_subscription.id, user_id=session.get('user_id')), cls="btn btn-error text-white btn-sm w-full") if product_id == active_subscription.product_id else
                    Button("Upgrade" if price_amount > active_subscription.amount else "Downgrade", name='change', id='change-btn', hx_post=f"/update-subscription", hx_vals=dict(subscription_id=active_subscription.id, user_id=session.get('user_id'), product_id=product_id), cls="btn btn-primary text-white btn-sm w-full") if product_id != active_subscription.product_id else
                    Button('Something Else!')
                )
            )
        ) for name, description, product_id, price_amount in products
    ]
    
    
    
    ## extremely simple content filter
    PRODUCT_MAP = {
        # product_id
        products[0][2]: 'static/assets/product1.jpg',
        products[1][2]: 'static/assets/product2.jpg',
    }
    
    if active_subscription:
        display = PRODUCT_MAP.get(active_subscription.product_id)
    else:
        display=None
    
    return Div(cls="min-h-screen flex items-center justify-center p-4")(
        Div(cls="w-full max-w-4xl mx-auto")(
            Div(cls="text-center mb-4")(H2("Authed!", cls="text-3xl font-bold text-primary mb-2"),P("session information", cls="text-base-content/70")),
            Div(cls="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4")(*session_cards),
            Div(cls="text-center mb-4")(H2("Products", cls="text-3xl font-bold text-primary mb-2")),  
            Div(cls="grid grid-cols-2 gap-4 mb-4")(*product_cards),
            
            Div(cls="text-center mb-4")(H2("You're Subscribed!", cls="text-3xl font-bold text-primary mb-2"),P("Here's your content:", cls="text-base-content/70"), Img(src=display)) if display else None,
            Div(cls="text-center mt-8")(Button("Revoke Subscription", hx_post=f"/revoke-subscription", hx_vals=dict(subscription_id=active_subscription.id), cls="btn btn-error text-white btn-lg")) if active_subscription else None,
            Div(cls="text-center mt-8")(A("Logout", href='/logout', cls="btn btn-primary btn-lg text-white"))
        )
    )
    
## polar webhook endpoint
@rt('/webhook')
async def post(request):
    try:
        body = await request.body() 
        event = validate_event(
            body=body,
            headers=request.headers,
            secret=os.getenv('POLAR_WEBHOOK_SECRET'),
        )
        print(type(event))
        return "", 202
    except WebhookVerificationError as e:
        print(e)
        return "", 403

if __name__ == "__main__":
    serve(port=PORT)
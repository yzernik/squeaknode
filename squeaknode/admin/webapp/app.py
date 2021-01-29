import logging
import os

from flask import flash
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask_cors import CORS
from flask_login import current_user
from flask_login import login_required
from flask_login import login_user
from flask_login import LoginManager
from flask_login import logout_user

from proto import lnd_pb2
from proto import squeak_admin_pb2
from squeaknode.admin.webapp.forms import LoginForm
from squeaknode.admin.webapp.squeak_admin_web_user import User

logger = logging.getLogger(__name__)


def create_app(handler, username, password):
    # create and configure the app
    logger.info("Starting flask app from directory: {}".format(os.getcwd()))
    app = Flask(
        __name__,
        static_url_path="/",
        static_folder="static/build",
    )
    app.config.from_mapping(
        SECRET_KEY="dev",
    )
    login = LoginManager(app)
    valid_user = User(
        username,
        password,
    )
    logger.info("Starting flask with app.root_path: {}".format(app.root_path))
    logger.info("Files in root path: {}".format(os.listdir(app.root_path)))

    @login.user_loader
    def load_user(id):
        return valid_user.get_user_by_username(id)

    @login.unauthorized_handler
    def unauthorized_callback():
        return redirect("/login")

    def handle_request(request_message, handle_rpc_request):
        data = request.get_data()
        request_message.ParseFromString(data)
        try:
            reply = handle_rpc_request(request_message)
            return reply.SerializeToString()
        except Exception as e:
            logger.error("Error in handle admin web request.", exc_info=True)
            return str(e), 500

    @app.route("/login", methods=["GET", "POST"])
    def login():
        logger.info("Trying to login")
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        if form.validate_on_submit():
            user = valid_user.get_user_by_username(form.username.data)
            if user is None or not user.check_password(form.password.data):
                flash("Invalid username or password")
                return redirect(url_for("login"))
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for("index"))
        return render_template("login.html", title="Sign In", form=form)

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/")
    @login_required
    def index():
        logger.info("Getting index route.")
        return app.send_static_file("index.html")

    @app.route("/user")
    @login_required
    def user():
        logger.info("Getting user.")
        return current_user.username

    @app.route("/hello")
    @login_required
    def hello_world():
        logger.info("Getting hello route.")
        return "Hello, World!"

    @app.route("/lndgetinfo", methods=["POST"])
    @login_required
    def lndgetinfo():
        return handle_request(
            lnd_pb2.GetInfoRequest(),
            handler.handle_lnd_get_info,
        )

    @app.route("/lndwalletbalance", methods=["POST"])
    @login_required
    def lndwalletbalance():
        return handle_request(
            lnd_pb2.WalletBalanceRequest(),
            handler.handle_lnd_wallet_balance,
        )

    @app.route("/lndgettransactions", methods=["POST"])
    @login_required
    def lndgettransactions():
        return handle_request(
            lnd_pb2.GetTransactionsRequest(),
            handler.handle_lnd_get_transactions,
        )

    @app.route("/lndlistpeers", methods=["POST"])
    @login_required
    def lndlistpeers():
        return handle_request(
            lnd_pb2.ListPeersRequest(),
            handler.handle_lnd_list_peers,
        )

    @app.route("/lndlistchannels", methods=["POST"])
    @login_required
    def lndlistchannels():
        return handle_request(
            lnd_pb2.ListChannelsRequest(),
            handler.handle_lnd_list_channels,
        )

    @app.route("/lndpendingchannels", methods=["POST"])
    @login_required
    def lndpendingchannels():
        return handle_request(
            lnd_pb2.PendingChannelsRequest(),
            handler.handle_lnd_pending_channels,
        )

    @app.route("/lndconnectpeer", methods=["POST"])
    @login_required
    def lndconnectpeer():
        return handle_request(
            lnd_pb2.ConnectPeerRequest(),
            handler.handle_lnd_connect_peer,
        )

    @app.route("/lnddisconnectpeer", methods=["POST"])
    @login_required
    def lnddisconnectpeer():
        return handle_request(
            lnd_pb2.DisconnectPeerRequest(),
            handler.handle_lnd_disconnect_peer,
        )

    @app.route("/lndopenchannelsync", methods=["POST"])
    @login_required
    def lndopenchannelsync():
        return handle_request(
            lnd_pb2.OpenChannelRequest(),
            handler.handle_lnd_open_channel_sync,
        )

    @app.route("/lndclosechannel", methods=["POST"])
    @login_required
    def lndclosechannel():
        return handle_request(
            lnd_pb2.CloseChannelRequest(),
            handler.handle_lnd_close_channel,
        )

    @app.route("/lndnewaddress", methods=["POST"])
    @login_required
    def lndnewaddress():
        return handle_request(
            lnd_pb2.NewAddressRequest(),
            handler.handle_lnd_new_address,
        )

    @app.route("/lndsendcoins", methods=["POST"])
    @login_required
    def lndsendcoins():
        return handle_request(
            lnd_pb2.SendCoinsRequest(),
            handler.handle_lnd_send_coins,
        )

    @app.route("/gettimelinesqueakdisplays", methods=["POST"])
    @login_required
    def gettimelinesqueakdisplays():
        return handle_request(
            squeak_admin_pb2.GetTimelineSqueakDisplaysRequest(),
            handler.handle_get_timeline_squeak_display_entries,
        )

    @app.route("/getsqueakprofile", methods=["POST"])
    @login_required
    def getsqueakprofile():
        return handle_request(
            squeak_admin_pb2.GetSqueakProfileRequest(),
            handler.handle_get_squeak_profile,
        )

    @app.route("/setsqueakprofilefollowing", methods=["POST"])
    @login_required
    def setsqueakprofilefollowing():
        return handle_request(
            squeak_admin_pb2.SetSqueakProfileFollowingRequest(),
            handler.handle_set_squeak_profile_following,
        )

    @app.route("/setsqueakprofilesharing", methods=["POST"])
    @login_required
    def setsqueakprofilesharing():
        return handle_request(
            squeak_admin_pb2.SetSqueakProfileSharingRequest(),
            handler.handle_set_squeak_profile_sharing,
        )

    @app.route("/renamesqueakprofile", methods=["POST"])
    @login_required
    def renamesqueakprofile():
        return handle_request(
            squeak_admin_pb2.RenameSqueakProfileRequest(),
            handler.handle_rename_squeak_profile,
        )

    @app.route("/getpeers", methods=["POST"])
    @login_required
    def getpeers():
        return handle_request(
            squeak_admin_pb2.GetPeersRequest(),
            handler.handle_get_squeak_peers,
        )

    @app.route("/payoffer", methods=["POST"])
    @login_required
    def payoffer():
        return handle_request(
            squeak_admin_pb2.PayOfferRequest(),
            handler.handle_pay_offer,
        )

    @app.route("/getbuyoffers", methods=["POST"])
    @login_required
    def getbuyoffers():
        return handle_request(
            squeak_admin_pb2.GetBuyOffersRequest(),
            handler.handle_get_buy_offers,
        )

    @app.route("/getbuyoffer", methods=["POST"])
    @login_required
    def getbuyoffer():
        return handle_request(
            squeak_admin_pb2.GetBuyOfferRequest(),
            handler.handle_get_buy_offer,
        )

    @app.route("/getpeer", methods=["POST"])
    @login_required
    def getpeer():
        return handle_request(
            squeak_admin_pb2.GetPeerRequest(),
            handler.handle_get_squeak_peer,
        )

    @app.route("/setpeerdownloading", methods=["POST"])
    @login_required
    def setpeerdownloading():
        return handle_request(
            squeak_admin_pb2.SetPeerDownloadingRequest(),
            handler.handle_set_squeak_peer_downloading,
        )

    @app.route("/setpeeruploading", methods=["POST"])
    @login_required
    def setpeeruploading():
        return handle_request(
            squeak_admin_pb2.SetPeerUploadingRequest(),
            handler.handle_set_squeak_peer_uploading,
        )

    @app.route("/renamepeer", methods=["POST"])
    @login_required
    def renamepeer():
        return handle_request(
            squeak_admin_pb2.RenamePeerRequest(),
            handler.handle_rename_squeak_peer,
        )

    @app.route("/getsigningprofiles", methods=["POST"])
    @login_required
    def getsigningprofiles():
        return handle_request(
            squeak_admin_pb2.GetSigningProfilesRequest(),
            handler.handle_get_signing_profiles,
        )

    @app.route("/getcontactprofiles", methods=["POST"])
    @login_required
    def getcontactprofiles():
        return handle_request(
            squeak_admin_pb2.GetContactProfilesRequest(),
            handler.handle_get_contact_profiles,
        )

    @app.route("/makesqueakrequest", methods=["POST"])
    @login_required
    def makesqueakrequest():
        return handle_request(
            squeak_admin_pb2.MakeSqueakRequest(),
            handler.handle_make_squeak,
        )

    @app.route("/getsqueakdisplay", methods=["POST"])
    @login_required
    def getsqueakdisplay():
        return handle_request(
            squeak_admin_pb2.GetSqueakDisplayRequest(),
            handler.handle_get_squeak_display_entry,
        )

    @app.route("/getancestorsqueakdisplays", methods=["POST"])
    @login_required
    def getancestorsqueakdisplays():
        return handle_request(
            squeak_admin_pb2.GetAncestorSqueakDisplaysRequest(),
            handler.handle_get_ancestor_squeak_display_entries,
        )

    @app.route("/getreplysqueakdisplays", methods=["POST"])
    @login_required
    def getreplysqueakdisplays():
        return handle_request(
            squeak_admin_pb2.GetReplySqueakDisplaysRequest(),
            handler.handle_get_reply_squeak_display_entries,
        )

    @app.route("/getsqueakprofilebyaddress", methods=["POST"])
    @login_required
    def getsqueakprofilebyaddress():
        return handle_request(
            squeak_admin_pb2.GetSqueakProfileByAddressRequest(),
            handler.handle_get_squeak_profile_by_address,
        )

    @app.route("/getaddresssqueakdisplays", methods=["POST"])
    @login_required
    def getaddresssqueakdisplays():
        return handle_request(
            squeak_admin_pb2.GetAddressSqueakDisplaysRequest(),
            handler.handle_get_squeak_display_entries_for_address,
        )

    @app.route("/createcontactprofile", methods=["POST"])
    @login_required
    def createcontactprofile():
        return handle_request(
            squeak_admin_pb2.CreateContactProfileRequest(),
            handler.handle_create_contact_profile,
        )

    @app.route("/createsigningprofile", methods=["POST"])
    @login_required
    def createsigningprofile():
        return handle_request(
            squeak_admin_pb2.CreateSigningProfileRequest(),
            handler.handle_create_signing_profile,
        )

    @app.route("/importsigningprofile", methods=["POST"])
    @login_required
    def importsigningprofile():
        return handle_request(
            squeak_admin_pb2.ImportSigningProfileRequest(),
            handler.handle_import_signing_profile,
        )

    @app.route("/createpeer", methods=["POST"])
    @login_required
    def createpeer():
        return handle_request(
            squeak_admin_pb2.CreatePeerRequest(),
            handler.handle_create_peer,
        )

    @app.route("/deletepeer", methods=["POST"])
    @login_required
    def deletepeer():
        return handle_request(
            squeak_admin_pb2.DeletePeerRequest(),
            handler.handle_delete_squeak_peer,
        )

    @app.route("/deleteprofile", methods=["POST"])
    @login_required
    def deleteprofile():
        return handle_request(
            squeak_admin_pb2.DeleteSqueakProfileRequest(),
            handler.handle_delete_squeak_profile,
        )

    @app.route("/deletesqueak", methods=["POST"])
    @login_required
    def deletesqueak():
        return handle_request(
            squeak_admin_pb2.DeleteSqueakRequest(),
            handler.handle_delete_squeak,
        )

    @app.route("/syncsqueak", methods=["POST"])
    @login_required
    def syncsqueak():
        return handle_request(
            squeak_admin_pb2.SyncSqueakRequest(),
            handler.handle_sync_squeak,
        )

    @app.route("/getsqueakdetails", methods=["POST"])
    @login_required
    def getsqueakdetails():
        return handle_request(
            squeak_admin_pb2.GetSqueakDetailsRequest(),
            handler.handle_get_squeak_details,
        )

    @app.route("/getsentpayments", methods=["POST"])
    @login_required
    def getsentpayments():
        return handle_request(
            squeak_admin_pb2.GetSentPaymentsRequest(),
            handler.handle_get_sent_payments,
        )

    @app.route("/getsentoffers", methods=["POST"])
    @login_required
    def getsentoffers():
        return handle_request(
            squeak_admin_pb2.GetSentOffersRequest(),
            handler.handle_get_sent_offers,
        )

    @app.route("/getreceivedpayments", methods=["POST"])
    @login_required
    def getreceivedpayments():
        return handle_request(
            squeak_admin_pb2.GetReceivedPaymentsRequest(),
            handler.handle_get_received_payments,
        )

    @app.route("/getnetwork", methods=["POST"])
    @login_required
    def getnetwork():
        return handle_request(
            squeak_admin_pb2.GetNetworkRequest(),
            handler.handle_get_network,
        )

    @app.route("/getsqueakprofileprivatekey", methods=["POST"])
    @login_required
    def getsqueakprofileprivatekey():
        return handle_request(
            squeak_admin_pb2.GetSqueakProfilePrivateKeyRequest(),
            handler.handle_get_squeak_profile_private_key,
        )

    @app.route("/getpaymentsummary", methods=["POST"])
    @login_required
    def getpaymentsummary():
        return handle_request(
            squeak_admin_pb2.GetPaymentSummaryRequest(),
            handler.handle_get_payment_summary,
        )

    return app


class SqueakAdminWebServer:
    def __init__(
        self,
        host,
        port,
        username,
        password,
        use_ssl,
        login_required,
        allow_cors,
        handler,
    ):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.login_required = login_required
        self.allow_cors = allow_cors
        self.app = create_app(handler, username, password)

    def serve(self):
        # Set LOGIN_REQUIRED and allow CORS if login not required.
        if not self.login_required:
            self.app.config["LOGIN_DISABLED"] = True

        # Allow CORS
        if self.allow_cors:
            CORS(self.app)

        self.app.run(
            self.host,
            self.port,
            debug=False,
            ssl_context="adhoc" if self.use_ssl else None,
        )

"""
Firebase Cloud Messaging (FCM) Utility
Handles Firebase Admin SDK initialization and push notification delivery.
"""
import os
import firebase_admin
from firebase_admin import credentials, messaging
from utils.logger import get_logger

logger = get_logger(__name__)

_firebase_initialized = False


def _init_firebase():
    """Initialize Firebase Admin SDK (singleton). Safe to call multiple times."""
    global _firebase_initialized
    if _firebase_initialized:
        return

    # Priority order for service account JSON:
    # 1. FCM_SERVICE_ACCOUNT_PATH env var (explicit file path)
    # 2. GOOGLE_APPLICATION_CREDENTIALS env var (standard Google SDK var)
    # 3. Default: backend/config/firebase-service-account.json
    sa_path = os.environ.get(
        "FCM_SERVICE_ACCOUNT_PATH",
        os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "firebase-service-account.json")
        )
    )

    if not os.path.isfile(sa_path):
        logger.error(
            f"Firebase service account file not found at: {sa_path}. "
            "Push notifications will NOT work. "
            "Set FCM_SERVICE_ACCOUNT_PATH or place the file at config/firebase-service-account.json"
        )
        return

    try:
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info(f"Firebase initialized successfully from {sa_path}")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
    image: str | None = None,
) -> bool:
    """
    Send a push notification to a single device via FCM.
    Returns True on success, False on failure.
    """
    _init_firebase()
    if not _firebase_initialized:
        logger.warning("Firebase not initialized — skipping push notification")
        return False

    try:
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image,
        )

        # Convert all data values to strings (FCM requirement)
        str_data = {k: str(v) for k, v in (data or {}).items() if v is not None}

        message = messaging.Message(
            notification=notification,
            data=str_data,
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    click_action="FLUTTER_NOTIFICATION_CLICK",
                    channel_id="96sooq_notifications",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                        content_available=True,
                    ),
                ),
            ),
        )

        response = messaging.send(message)
        logger.info(f"Push sent OK: {response}")
        return True

    except messaging.UnregisteredError:
        logger.warning(f"FCM token unregistered (stale): {token[:20]}...")
        return False
    except messaging.InvalidArgumentError as e:
        logger.error(f"FCM invalid argument: {e}")
        return False
    except Exception as e:
        logger.error(f"FCM send error: {e}")
        return False


def send_push_to_multiple(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
    image: str | None = None,
) -> list[str]:
    """
    Send push notification to multiple devices.
    Returns list of tokens that failed (stale/invalid — should be deactivated).
    """
    _init_firebase()
    if not _firebase_initialized:
        logger.warning("Firebase not initialized — skipping batch push")
        return []

    if not tokens:
        return []

    str_data = {k: str(v) for k, v in (data or {}).items() if v is not None}

    notification = messaging.Notification(
        title=title,
        body=body,
        image=image,
    )

    message = messaging.MulticastMessage(
        notification=notification,
        data=str_data,
        tokens=tokens,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                sound="default",
                click_action="FLUTTER_NOTIFICATION_CLICK",
                channel_id="96sooq_notifications",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound="default",
                    badge=1,
                    content_available=True,
                ),
            ),
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message)
        logger.info(f"Multicast: {response.success_count} sent, {response.failure_count} failed")

        failed_tokens = []
        for idx, send_response in enumerate(response.responses):
            if not send_response.success:
                error = send_response.exception
                if isinstance(error, (messaging.UnregisteredError, messaging.InvalidArgumentError)):
                    failed_tokens.append(tokens[idx])
                logger.warning(f"Token {tokens[idx][:20]}... failed: {error}")

        return failed_tokens

    except Exception as e:
        logger.error(f"Multicast send error: {e}")
        return []

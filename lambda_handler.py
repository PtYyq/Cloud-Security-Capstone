import os
import json
import uuid
import logging
import boto3
from botocore.exceptions import ClientError

# -------- Global config --------
PAB_ENFORCED = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True,
}
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")

s3 = boto3.client("s3")
sns = boto3.client("sns")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALL_USERS_URIS = {
    "http://acs.amazonaws.com/groups/global/AllUsers",
    "https://acs.amazonaws.com/groups/global/AllUsers",
}

# -------- Entry --------
def lambda_handler(event, context):
    incident_id = str(uuid.uuid4())
    logger.info(json.dumps({"incident_id": incident_id, "event": event}, default=str))

    target_buckets = extract_buckets_from_event(event)
    findings = collect_security_data(target_buckets=target_buckets)  # -> List[str] (public buckets)
    risks = analyze_findings(findings)                               # -> List[str]

    actions = respond_to_risks(risks) if risks else []
    send_notification(findings, risks, actions, incident_id)

    return {
        "statusCode": 200,
        "findings_count": len(findings),
        "risk_count": len(risks),
        "dry_run": DRY_RUN,
        "incident_id": incident_id,
    }

# -------- Helpers --------
def extract_buckets_from_event(event):
    """extract bucket from EventBridge/CloudTrail"""
    try:
        d = event.get("detail", {})
        if d.get("eventSource") == "s3.amazonaws.com":
            name = (d.get("requestParameters") or {}).get("bucketName")
            return [name] if name else []
    except Exception:
        pass
    return []

# -------- Step 1: Collect --------
def collect_security_data(target_buckets=None):
    if target_buckets:
        bucket_names = target_buckets
    else:
        bucket_names = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]

    return check_public_buckets(bucket_names)

def check_public_buckets(bucket_names):
    public_buckets = []
    for name in bucket_names:
        try:
            acl = s3.get_bucket_acl(Bucket=name)
            grants = acl.get("Grants", [])
            if any(
                g.get("Grantee", {}).get("Type") == "Group"
                and g["Grantee"].get("URI") in ALL_USERS_URIS
                for g in grants
            ):
                public_buckets.append(name)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code not in ("AccessDenied", "NoSuchBucket"):
                logger.warning(f"[WARN] get_bucket_acl({name}) -> {str(e)[:160]}")
    return public_buckets

# -------- Step 2: Analyze --------
def analyze_findings(findings):
    return list(findings)

# -------- Step 3: Respond --------
def respond_to_risks(risks):
    actions = []
    for b in risks:
        plan = {"bucket": b, "action": "PutPublicAccessBlock", "config": PAB_ENFORCED, "dry_run": DRY_RUN}
        if DRY_RUN:
            logger.info(f"[DRY-RUN] Would enforce PAB on {b}")
            actions.append(plan)
            continue
        try:
            s3.put_public_access_block(Bucket=b, PublicAccessBlockConfiguration=PAB_ENFORCED)
            plan["result"] = "applied"
            logger.info(f"[APPLIED] Enforced PAB on {b}")
        except ClientError as e:
            plan["result"] = f"error:{str(e)}"
            logger.error(f"[ERROR] Enforce PAB on {b} failed: {e}")
        actions.append(plan)
    return actions

# -------- Step 4: Notify --------
def send_notification(findings, risks, actions, incident_id):
    subject = f"[S3 IR] {'DRY-RUN ' if DRY_RUN else ''}Public ACL Auto-Remediation | risks={len(risks)}"
    body = {
        "incident_id": incident_id,
        "dry_run": DRY_RUN,
        "scanned_buckets": len(findings),
        "risk_buckets": risks,
        "actions": actions
    }
    msg = json.dumps(body, indent=2)
    logger.info(msg)

    if not SNS_TOPIC_ARN:
        logger.info("SNS_TOPIC_ARN not set; skip SNS publish.")
        return
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=msg)
    except ClientError as e:
        logger.error(f"SNS publish failed: {e}")

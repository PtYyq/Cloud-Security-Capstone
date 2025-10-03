REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TRAIL_BUCKET="ct-logs-$ACCOUNT_ID-$REGION-$(date +%Y%m%d%H%M%S)"

aws s3api create-bucket --bucket "$TRAIL_BUCKET" --region "$REGION" || true

cat > ct-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": { "Service": "cloudtrail.amazonaws.com" },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::$TRAIL_BUCKET"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": { "Service": "cloudtrail.amazonaws.com" },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::$TRAIL_BUCKET/AWSLogs/$ACCOUNT_ID/*",
      "Condition": { "StringEquals": { "s3:x-amz-acl": "bucket-owner-full-control" } }
    }
  ]
}
EOF

aws s3api put-bucket-policy --bucket "$TRAIL_BUCKET" --policy file://ct-bucket-policy.json

aws cloudtrail create-trail --name MedTechTrail \
  --s3-bucket-name "$TRAIL_BUCKET" \
  --is-multi-region-trail

aws cloudtrail put-event-selectors --trail-name MedTechTrail \
  --event-selectors '[{"ReadWriteType":"All","IncludeManagementEvents":true}]'

aws cloudtrail start-logging --name MedTechTrail

aws cloudtrail get-trail-status --name MedTechTrail

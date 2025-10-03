REGION=us-east-1
BUCKET="ir-test-$(date +%Y%m%d%H%M%S)"

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
echo "BUCKET=$BUCKET"

# enable ACL
aws s3api put-bucket-ownership-controls \
  --bucket "$BUCKET" \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerPreferred}]'

# write PAB（generate PutPublicAccessBlock event）
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
'{"BlockPublicAcls":true,"IgnorePublicAcls":true,"BlockPublicPolicy":true,"RestrictPublicBuckets":true}'

# Delete PAB（generate DeletePublicAccessBlock event)
aws s3api delete-public-access-block --bucket "$BUCKET"

# try to make ACL public(generate PutBucketAcl event）
aws s3api put-bucket-acl --bucket "$BUCKET" --acl public-read || true

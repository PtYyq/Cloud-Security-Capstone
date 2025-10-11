# make public read
aws s3api put-bucket-acl --bucket ir-test-20251010200516 --acl public-read

# dynamodb query
aws dynamodb scan \
  --table-name S3AutoRemediationIncidents \
  --max-items 20 \
  --projection-expression "incident_id, #ts, dry_run, scanned_buckets, risk_buckets, actions" \
  --expression-attribute-names '{"#ts":"timestamp"}' \
  --output table

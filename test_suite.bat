docker exec django_api python /app/e2e_test.py > e2e_result.txt 2>&1
docker logs --tail 10 sync_publisher > pub_out.txt 2>&1
docker logs --tail 10 sync_consumer > con_out.txt 2>&1

cd /home/user/work/robot_percept
for e in robot_percept robot_percept_g0c; do
 /home/user/anaconda3/envs/$e/bin/python -m pip freeze > bench/verify_g1/freeze_$e.txt 2>&1
 echo $e $(wc -l < bench/verify_g1/freeze_$e.txt) $(sha256sum < bench/verify_g1/freeze_$e.txt)
done
grep -E '^(torch|torchvision|numpy|transformers)==' bench/verify_g1/freeze_robot_percept_g0c.txt

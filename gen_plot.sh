INPUT=results
OUTPUT=rate
OUTPUT2=utilization
python plot_rate_128.py --input $INPUT --out $OUTPUT
python plot_utilization_128.py --input $INPUT --out $OUTPUT2

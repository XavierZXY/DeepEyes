import pandas as pd
df = pd.read_parquet('/app/datasets/IRdatasetv3/shard-train-000000.parquet')  # optional engine='pyarrow'
print(df.columns.tolist())
print(df.head(5))
print(df['env_name'],666)
# print(df.at[4, 'reward_model'],99)
# print(df.at[4, 'reward_model'][0],98)
# print(df.at[0, 'images'][0]["bytes"],555)
# print(df.at[0, 'prompt'][0]['content'],444)
# print(df.at[0, 'prompt'][1]['content'],222)

# print(df.at[0,'extra_info'],333)
print(df.dtypes)
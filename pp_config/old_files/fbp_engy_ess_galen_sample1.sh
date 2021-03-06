#!/usr/bin/env bash
REPO=/export/home/srasp/repositories/CBRAIN-CAM/

python $REPO/cbrain/preprocess_aqua.py \
--config_file $REPO/pp_config/fbp_engy_ess_galen.yml \
--in_dir /beegfs/DATA/pritchard/gyacalis/aquaplanet/galen_sp/daily_files/ \
--aqua_names='*.h1.0000-*-0[5-9]-*' \
--out_dir /scratch/srasp/preprocessed_data/ \
--out_pref fbp_engy_ess_galen_train_sample1 &&
python $REPO/cbrain/preprocess_aqua.py \
--config_file $REPO/pp_config/fbp_engy_ess_galen.yml \
--in_dir /beegfs/DATA/pritchard/gyacalis/aquaplanet/galen_sp/daily_files/ \
--aqua_names='*.h1.0000-*-2[1-5]-*' \
--out_dir /scratch/srasp/preprocessed_data/ \
--out_pref fbp_engy_ess_galen_valid_sample1 \
--ext_norm /scratch/srasp/preprocessed_data/fbp_engy_ess_galen_train_sample1_norm.nc &&
python $REPO/cbrain/shuffle_ds.py \
--pref /scratch/srasp/preprocessed_data/fbp_engy_ess_galen_train_sample1
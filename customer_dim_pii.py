import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe  import DynamicFrame
from pyspark.sql.functions import current_timestamp
import pyspark

args = getResolvedOptions(sys.argv, ['TempDir','JOB_NAME'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

datasource0 = glueContext.create_dynamic_frame.from_catalog(database = "glue_db", table_name = "tb_addresses_processed", transformation_ctx = "datasource0")
baseline_addresses=datasource0.toDF()
baseline_addresses.registerTempTable("baseline_addresses")
baselined_addresses=spark.sql("""select distinct cast(replace(substring(trim(createdts),1,23),'T',' ') as timestamp) as createdts,
cast(replace(substring(trim(modifiedts),1,23),'T',' ') as timestamp) as modifiedts,
cast(ownerpkstring as bigint) as ownerpkstring,cast(pk as bigint) as pk,
p_cellphone,p_district,p_postalcode,p_streetname,p_streetnumber,p_town,p_addresstype,p_addressline3 
from (select createdts,modifiedts,ownerpkstring,pk,p_cellphone,p_district,p_postalcode,p_streetname,p_streetnumber,p_town,p_addresstype,p_addressline3,
row_number() over (partition by pk order by modifiedts desc ) as rank from baseline_addresses) where rank=1""")
baselined_addresses.registerTempTable("baselined_addresses")


datasource1 = glueContext.create_dynamic_frame.from_catalog(database = "glue_db", table_name = "tb_users_processed", transformation_ctx = "datasource1")
baseline_users=datasource1.toDF()
baseline_users.registerTempTable("baseline_users")
baselined_users=spark.sql("""select distinct modifiedts,cast(pk as bigint) as pk,cast(p_uid as integer) as p_uid,cast(p_defaultpaymentaddress as bigint) as p_defaultpaymentaddress,
cast(p_defaultshipmentaddress as bigint) as p_defaultshipmentaddress,p_originaluid,cast(substring(trim(p_dateofbirth),1,10) as date) as p_dateofbirth,
p_mobilenumber,cast(substring(trim(p_dateofanniversary),1,10) as date) as p_dateofanniversary,p_firstname,p_lastname,p_nickname,p_qcverifymobileno 
from 
(select modifiedts,pk,p_uid,p_defaultpaymentaddress,p_defaultshipmentaddress,p_originaluid,p_dateofbirth,p_mobilenumber,p_dateofanniversary,p_firstname,p_lastname,
p_nickname,p_qcverifymobileno,rank() over (partition by pk order by modifiedts desc ) as rank from baseline_users) where rank=1""")
baselined_users.registerTempTable("baselined_users")


datasource2 = glueContext.create_dynamic_frame.from_catalog(database = "glue_redshift_tb", table_name = "dldb_tuldlmrt_mvp2_customer_dim", redshift_tmp_dir = args["TempDir"], transformation_ctx = "datasource2")
dff1=datasource2.toDF()
dff1.registerTempTable("dff1")


joinsparksqldf1=spark.sql("""select distinct case when f.customer_key is null then 0 else f.customer_key end as customer_key,
u.p_uid as customer_id,
nullif(trim(u.p_originaluid),'0') as customer_email,
nullif(trim(u.p_firstname),'0') as first_name,
nullif(trim(u.p_lastname),'0') as last_name,
u.p_dateofbirth as date_of_birth,
u.p_dateofanniversary as date_of_anniversary,
nullif(trim(u.p_nickname),'0') as nick_name,
nullif(substring(trim(u.p_mobilenumber),1,20),'0') as customer_mobile,
nullif(trim(u.p_qcverifymobileno),'0') as qc_verified_mobile_no,
case when (u.p_defaultshipmentaddress) = (add.pk) then 1 else 0  end as default_shipping_address_flag,
case when (u.p_defaultpaymentaddress) = (add.pk) then 1 else 0 end as default_billing_address_flag,
replace(replace(nullif(trim(add.p_streetnumber),'0'), CHR(10), ''),CHR(13),'') as customer_address_line_1,
replace(replace(nullif(trim(add.p_streetname),'0'), CHR(10), ''),CHR(13),'')  as  customer_address_line_2,
replace(replace(nullif(trim(add.p_addressline3),'0'), CHR(10), ''),CHR(13),'') as  customer_address_line_3,
nullif(trim(add.p_town),'0') as customer_city,
nullif(trim(add.p_district),'0') as customer_state,
nullif(trim(add.p_postalcode),'0') as customer_pincode,
nullif(trim(add.p_cellphone),'0') as registered_cellphone,
nullif(trim(add.p_addresstype),'0') as customer_address_type,
add.pk as address_pk,
add.CREATEDTS as address_created_date_in_source,
add.MODIFIEDTS as address_last_modified_date_in_source,
from_utc_timestamp(current_timestamp,'Asia/Kolkata') as DW_CREATED_DATE,
from_utc_timestamp(current_timestamp,'Asia/Kolkata') as DW_LAST_MODIFIED_DATE
from baselined_users u 
left outer join baselined_addresses add on (u.pk) = (add.ownerpkstring)
left outer join (select max(customer_key) customer_key ,customer_id from dff1  group by customer_id) f on (f.customer_id)=(u.p_uid)
""")


dy_joinsparksqldf1 = DynamicFrame.fromDF(joinsparksqldf1, glueContext, "dy_joinsparksqldf1")


post_query="""begin;update tuldlmrt_mvp2.customer_dim_pii set 
customer_key=tuldlbse.customer_dim_pii_base.customer_key,
CUSTOMER_ID=tuldlbse.customer_dim_pii_base.CUSTOMER_ID,
CUSTOMER_EMAIL=tuldlbse.customer_dim_pii_base.CUSTOMER_EMAIL,
FIRST_NAME=tuldlbse.customer_dim_pii_base.FIRST_NAME,
LAST_NAME=tuldlbse.customer_dim_pii_base.LAST_NAME,
DATE_OF_BIRTH=tuldlbse.customer_dim_pii_base.DATE_OF_BIRTH,
DATE_OF_ANNIVERSARY=tuldlbse.customer_dim_pii_base.DATE_OF_ANNIVERSARY,
NICK_NAME=tuldlbse.customer_dim_pii_base.NICK_NAME,
CUSTOMER_MOBILE=tuldlbse.customer_dim_pii_base.CUSTOMER_MOBILE,
CUSTOMER_ADDRESS_LINE_1=tuldlbse.customer_dim_pii_base.CUSTOMER_ADDRESS_LINE_1,
CUSTOMER_ADDRESS_LINE_2=tuldlbse.customer_dim_pii_base.CUSTOMER_ADDRESS_LINE_2,
CUSTOMER_ADDRESS_LINE_3=tuldlbse.customer_dim_pii_base.CUSTOMER_ADDRESS_LINE_3,
CUSTOMER_CITY=tuldlbse.customer_dim_pii_base.CUSTOMER_CITY,
CUSTOMER_STATE=tuldlbse.customer_dim_pii_base.CUSTOMER_STATE,
CUSTOMER_PINCODE=tuldlbse.customer_dim_pii_base.CUSTOMER_PINCODE,
REGISTERED_CELLPHONE=tuldlbse.customer_dim_pii_base.REGISTERED_CELLPHONE,
CUSTOMER_ADDRESS_TYPE=tuldlbse.customer_dim_pii_base.CUSTOMER_ADDRESS_TYPE,
address_pk=tuldlbse.customer_dim_pii_base.address_pk,
QC_VERIFIED_MOBILE_NO=tuldlbse.customer_dim_pii_base.QC_VERIFIED_MOBILE_NO,
default_shipping_address_flag=tuldlbse.customer_dim_pii_base.default_shipping_address_flag,
default_billing_address_flag=tuldlbse.customer_dim_pii_base.default_billing_address_flag,
address_created_date_in_source=tuldlbse.customer_dim_pii_base.address_created_date_in_source,
address_last_modified_date_in_source=tuldlbse.customer_dim_pii_base.address_last_modified_date_in_source,
DW_LAST_MODIFIED_DATE=tuldlbse.customer_dim_pii_base.DW_LAST_MODIFIED_DATE 
from tuldlbse.customer_dim_pii_base 
where (tuldlbse.customer_dim_pii_base.customer_id)=(tuldlmrt_mvp2.customer_dim_pii.customer_id) and
(tuldlbse.customer_dim_pii_base.address_pk)=(tuldlmrt_mvp2.customer_dim_pii.address_pk) and
(tuldlbse.customer_dim_pii_base.address_last_modified_date_in_source)<>(tuldlmrt_mvp2.customer_dim_pii.address_last_modified_date_in_source);
insert into tuldlmrt_mvp2.customer_dim_pii(customer_key,CUSTOMER_ID,CUSTOMER_EMAIL,FIRST_NAME,LAST_NAME,DATE_OF_BIRTH,DATE_OF_ANNIVERSARY,NICK_NAME,CUSTOMER_MOBILE,CUSTOMER_ADDRESS_LINE_1,CUSTOMER_ADDRESS_LINE_2,CUSTOMER_ADDRESS_LINE_3,CUSTOMER_CITY,CUSTOMER_STATE,CUSTOMER_PINCODE,REGISTERED_CELLPHONE,CUSTOMER_ADDRESS_TYPE,address_pk,QC_VERIFIED_MOBILE_NO,default_shipping_address_flag,default_billing_address_flag,address_created_date_in_source,address_last_modified_date_in_source,DW_CREATED_DATE,DW_LAST_MODIFIED_DATE) 
select distinct base.customer_key,base.CUSTOMER_ID,base.CUSTOMER_EMAIL,base.FIRST_NAME,base.LAST_NAME,base.DATE_OF_BIRTH,base.DATE_OF_ANNIVERSARY,base.NICK_NAME,base.CUSTOMER_MOBILE,base.CUSTOMER_ADDRESS_LINE_1,base.CUSTOMER_ADDRESS_LINE_2,base.CUSTOMER_ADDRESS_LINE_3,base.CUSTOMER_CITY,base.CUSTOMER_STATE,base.CUSTOMER_PINCODE,base.REGISTERED_CELLPHONE,base.CUSTOMER_ADDRESS_TYPE,base.address_pk,base.QC_VERIFIED_MOBILE_NO,base.default_shipping_address_flag,base.default_billing_address_flag,base.address_created_date_in_source,base.address_last_modified_date_in_source,base.DW_CREATED_DATE,base.DW_LAST_MODIFIED_DATE
from tuldlbse.customer_dim_pii_base base left outer join tuldlmrt_mvp2.customer_dim_pii mart 
on (base.customer_id)=(mart.customer_id) and (base.address_pk)=(mart.address_pk)
where (mart.customer_id is null) or (mart.address_pk is null);end;"""


datasink4 = glueContext.write_dynamic_frame.from_jdbc_conf(frame = dy_joinsparksqldf1, catalog_connection = "Glue-Redshift-Connection", connection_options = {"preactions":"truncate table tuldlbse.customer_dim_pii_base ;","dbtable": "tuldlbse.customer_dim_pii_base", "database": "dldb","postactions":post_query}, redshift_tmp_dir = args["TempDir"], transformation_ctx = "datasink4")


job.commit()
baselined_users.unpersist()
baselined_addresses.unpersist()
job.commit()
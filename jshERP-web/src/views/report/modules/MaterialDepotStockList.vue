<template>
  <div ref="container">
    <a-modal
      :title="title"
      :width="900"
      :visible="visible"
      :getContainer="() => $refs.container"
      :maskStyle="{'top':'93px','left':'154px'}"
      :wrapClassName="wrapClassNameInfo()"
      :mask="isDesktop()"
      :maskClosable="false"
      @cancel="handleCancel"
      cancelText="关闭"
      style="top:100px;height: 80%;">
      <template slot="footer">
        <a-button key="back" @click="handleCancel">取消(ESC)</a-button>
      </template>
      <!-- 仓库库存汇总 -->
      <a-table
        bordered
        ref="table"
        size="middle"
        rowKey="id"
        :columns="columns"
        :dataSource="dataSource"
        :components="handleDrag(columns)"
        :pagination="ipagination"
        :loading="loading"
        :expandedRowKeys="expandedRowKeys"
        :expandRowByClick="false"
        @change="handleTableChange"
        @expand="onExpand">
        <template slot="expandedRowRender" slot-scope="record">
          <a-spin :spinning="batchLoadingMap[record.id]">
            <a-table
              v-if="batchDataMap[record.id] && batchDataMap[record.id].length > 0"
              size="small"
              bordered
              :columns="batchColumns"
              :dataSource="batchDataMap[record.id]"
              :pagination="false"
              rowKey="batchNumber">
            </a-table>
            <div v-else-if="!batchLoadingMap[record.id]" style="text-align:center;padding:10px;color:#999">
              该仓库暂无批次数据（可能未开启批号管理）
            </div>
          </a-spin>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>
<script>
  import { JeecgListMixin } from '@/mixins/JeecgListMixin'
  import JEllipsis from '@/components/jeecg/JEllipsis'
  import { mixinDevice } from '@/utils/mixin'
  import { getBatchNumberList } from '@/api/api'

  export default {
    name: "MaterialDepotStockList",
    mixins:[JeecgListMixin, mixinDevice],
    components: {
      JEllipsis
    },
    data () {
      return {
        title:"库存详情",
        visible: false,
        disableMixinCreated: true,
        toFromType: '',
        currentMaterialId: '',
        // 查询条件
        queryParam: {
          depotIds: '',
          materialId:'',
        },
        ipagination:{
          pageSizeOptions: ['10', '20', '30', '100', '200']
        },
        tabKey: "1",
        // 仓库汇总列
        columns: [
          {
            title: '#',
            dataIndex: '',
            key:'rowIndex',
            width:40,
            align:"center",
            customRender:function (t,r,index) {
              return parseInt(index)+1;
            }
          },
          { title: '仓库名称', dataIndex: 'depotName', width: 200},
          { title: '库存数量', dataIndex: 'currentNumber', width: 100},
          { title: '成本价', dataIndex: 'unitPrice', width: 100},
          { title: '库存金额', dataIndex: 'allPrice', width: 100}
        ],
        // 批次明细列
        batchColumns: [
          {
            title: '#',
            width: 40,
            align: 'center',
            customRender: function(t, r, index) { return parseInt(index) + 1; }
          },
          { title: '批次号', dataIndex: 'batchNumber', width: 150 },
          { title: '库存数量', dataIndex: 'totalNum', width: 100 },
          { title: '单位', dataIndex: 'commodityUnit', width: 60 },
          { title: '条码', dataIndex: 'barCode', width: 100 }
        ],
        // 批次数据展开控制
        expandedRowKeys: [],
        batchDataMap: {},
        batchLoadingMap: {},
        labelCol: {
          xs: { span: 1 },
          sm: { span: 2 },
        },
        wrapperCol: {
          xs: { span: 10 },
          sm: { span: 16 },
        },
        url: {
          list: "/material/getMaterialDepotStock"
        }
      }
    },
    created() {
    },
    methods: {
      getQueryParams() {
        let param = Object.assign({}, this.queryParam, this.isorter)
        param.field = this.getQueryField()
        param.materialId = this.currentMaterialId
        param.currentPage = this.ipagination.current
        param.pageSize = this.ipagination.pageSize
        return param
      },
      show(record, depotIds) {
        this.model = Object.assign({}, record);
        this.currentMaterialId = record.id
        this.visible = true;
        this.queryParam.depotIds = depotIds
        this.queryParam.materialId = record.id
        this.expandedRowKeys = []
        this.batchDataMap = {}
        this.batchLoadingMap = {}
        this.loadData(1)
      },
      onExpand(expanded, record) {
        if (expanded) {
          // 展开时加载该仓库的批次数据
          this.loadBatchData(record)
        } else {
          // 收起时从 expandedRowKeys 中移除
          const index = this.expandedRowKeys.indexOf(record.id)
          if (index > -1) {
            this.expandedRowKeys.splice(index, 1)
          }
        }
      },
      loadBatchData(record) {
        const depotId = record.depotId || record.id
        if (this.batchDataMap[record.id]) {
          // 已有缓存，直接展开
          if (!this.expandedRowKeys.includes(record.id)) {
            this.expandedRowKeys.push(record.id)
          }
          return
        }
        this.$set(this.batchLoadingMap, record.id, true)
        getBatchNumberList({
          name: '',
          materialId: this.currentMaterialId,
          depotId: depotId
        }).then((res) => {
          if (res && res.code === 200) {
            this.$set(this.batchDataMap, record.id, res.data.rows || [])
            if (!this.expandedRowKeys.includes(record.id)) {
              this.expandedRowKeys.push(record.id)
            }
          }
        }).finally(() => {
          this.$set(this.batchLoadingMap, record.id, false)
        })
      },
      close () {
        this.$emit('close');
        this.visible = false;
      },
      handleCancel () {
        this.close()
      },
      onDateOk(value) {
        console.log(value);
      }
    }
  }
</script>
<style scoped>
  @import '~@assets/less/common.less'
</style>

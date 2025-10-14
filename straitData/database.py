"""
数据库连接和操作模块
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import json

logger = logging.getLogger(__name__)

class StraitDataDB:
    """海峡数据数据库操作类"""
    
    def __init__(self, connection_string: str):
        """
        初始化数据库连接
        
        Args:
            connection_string: 数据库连接字符串
        """
        self.connection_string = connection_string
        self.engine = None
        self._connect()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self.engine = create_engine(self.connection_string)
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接成功")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    def execute_strait_query(self, cx: float, cy: float, length_x: float, length_y: float, angle: float) -> dict:
        """
        执行海峡数据查询
        
        Args:
            cx: 中心点经度
            cy: 中心点纬度
            length_x: 长方形 X 方向长度（米）
            length_y: 长方形 Y 方向宽度（米）
            angle: 顺时针旋转角度（度）
            
        Returns:
            dict: 查询结果
        """
        # 直接使用字符串格式化构建SQL，避免参数绑定问题
        sql_query = f"""
        WITH params AS (
          -- 海峡中心点和长方形参数
          SELECT
            {cx}::double precision AS cx,
            {cy}::double precision AS cy,
            {length_x}::double precision AS length_x,  -- 长方形 X 方向长度（米）
            {length_y}::double precision AS length_y,  -- 长方形 Y 方向宽度（米）
            {angle}::double precision AS angle           -- 顺时针旋转角度（度）
        ),
        rectangle AS (
          -- 生成旋转长方形覆盖海峡（修复 SRID 问题）
          SELECT ST_Transform(
                   ST_Translate(
                     ST_Rotate(
                       ST_SetSRID(   -- 给长方形几何指定 SRID 3857
                         ST_MakePolygon(
                           ST_MakeLine(ARRAY[
                             ST_MakePoint(-length_x/2, -length_y/2),
                             ST_MakePoint(length_x/2, -length_y/2),
                             ST_MakePoint(length_x/2, length_y/2),
                             ST_MakePoint(-length_x/2, length_y/2),
                             ST_MakePoint(-length_x/2, -length_y/2)
                           ])
                         ),
                         3857
                       ),
                       radians(angle)  -- 顺时针旋转角度，弧度
                     ),
                     cx_3857, cy_3857
                   ),
                   4326  -- 投回 WGS84
                 ) AS geom
          FROM (
            SELECT *,
                   ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(cx, cy),4326),3857)) AS cx_3857,
                   ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(cx, cy),4326),3857)) AS cy_3857
            FROM params
          ) p
        ),
        coastline_lines AS (
          -- 获取长方形范围内的海岸线并合并
          SELECT ST_Union(c.geom) AS geom
          FROM coastline c, rectangle r
          WHERE ST_Intersects(c.geom, r.geom)
        ),
        split_result AS (
          -- 用海岸线切割长方形
          SELECT (ST_Dump(
                    ST_Split(r.geom, cl.geom)
                  )).geom AS geom
          FROM rectangle r, coastline_lines cl
        ),
        biggest_polygon AS (
          -- 选面积最大的 polygon（通常是海峡水域）
          SELECT geom
          FROM split_result
          ORDER BY ST_Area(geom) DESC
          LIMIT 1
        )
        SELECT jsonb_build_object(
          'type','FeatureCollection',
          'features', jsonb_build_array(
            jsonb_build_object(
              'type','Feature',
              'geometry', ST_AsGeoJSON(geom)::jsonb,
              'properties', jsonb_build_object('source','largest_split_polygon_rectangle')
            )
          )
        ) AS geojson
        FROM biggest_polygon;
        """
        
        try:
            with self.engine.connect() as conn:
                # 直接执行SQL（参数已通过f-string嵌入）
                result = conn.execute(text(sql_query))
                
                row = result.fetchone()
                if row and row[0]:
                    # 解析 JSON 结果
                    geojson_data = row[0]
                    logger.info(f"✅ 查询成功，返回 GeoJSON 数据")
                    return {
                        "success": True,
                        "data": geojson_data,
                        "message": "查询成功"
                    }
                else:
                    logger.warning("⚠️ 查询无结果")
                    return {
                        "success": False,
                        "data": None,
                        "message": "查询无结果"
                    }
                    
        except SQLAlchemyError as e:
            logger.error(f"❌ 数据库查询失败: {e}")
            return {
                "success": False,
                "data": None,
                "message": f"数据库查询失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ 查询执行失败: {e}")
            return {
                "success": False,
                "data": None,
                "message": f"查询执行失败: {str(e)}"
            }
    
    def store_strait_data(self, name: str, cx: float, cy: float, length_x: float, length_y: float, angle: float) -> dict:
        """
        存储海峡数据到数据库
        
        Args:
            name: 海峡名称
            cx: 中心点经度
            cy: 中心点纬度
            length_x: 长方形 X 方向长度（米）
            length_y: 长方形 Y 方向宽度（米）
            angle: 顺时针旋转角度（度）
            
        Returns:
            dict: 存储结果
        """
        # 构建INSERT SQL，使用与查询相同的几何计算逻辑
        insert_sql = f"""
        INSERT INTO straits (name, x, y, geom)
        WITH params AS (
          -- 海峡中心点和长方形参数
          SELECT
            {cx}::double precision AS cx,
            {cy}::double precision AS cy,
            {length_x}::double precision AS length_x,  -- 长方形 X 方向长度（米）
            {length_y}::double precision AS length_y,  -- 长方形 Y 方向宽度（米）
            {angle}::double precision AS angle           -- 顺时针旋转角度（度）
        ),
        rectangle AS (
          -- 生成旋转长方形覆盖海峡（修复 SRID 问题）
          SELECT ST_Transform(
                   ST_Translate(
                     ST_Rotate(
                       ST_SetSRID(
                         ST_MakePolygon(
                           ST_MakeLine(ARRAY[
                             ST_MakePoint(-length_x/2, -length_y/2),
                             ST_MakePoint(length_x/2, -length_y/2),
                             ST_MakePoint(length_x/2, length_y/2),
                             ST_MakePoint(-length_x/2, length_y/2),
                             ST_MakePoint(-length_x/2, -length_y/2)
                           ])
                         ),
                         3857
                       ),
                       radians(angle)
                     ),
                     cx_3857, cy_3857
                   ),
                   4326
                 ) AS geom
          FROM (
            SELECT *,
                   ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(cx, cy),4326),3857)) AS cx_3857,
                   ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(cx, cy),4326),3857)) AS cy_3857
            FROM params
          ) p
        ),
        coastline_lines AS (
          -- 获取长方形范围内的海岸线并合并
          SELECT ST_Union(c.geom) AS geom
          FROM coastline c, rectangle r
          WHERE ST_Intersects(c.geom, r.geom)
        ),
        split_result AS (
          -- 用海岸线切割长方形
          SELECT (ST_Dump(
                    ST_Split(r.geom, cl.geom)
                  )).geom AS geom
          FROM rectangle r, coastline_lines cl
        ),
        biggest_polygon AS (
          -- 选面积最大的 polygon（通常是海峡水域）
          SELECT geom
          FROM split_result
          ORDER BY ST_Area(geom) DESC
          LIMIT 1
        )
        SELECT
          '{name}'::text AS name,
          {cx}::double precision AS x,
          {cy}::double precision AS y,
          geom
        FROM biggest_polygon;
        """
        
        try:
            with self.engine.connect() as conn:
                # 执行插入操作
                result = conn.execute(text(insert_sql))
                conn.commit()
                
                # 获取插入的行数
                affected_rows = result.rowcount
                
                logger.info(f"✅ 海峡数据存储成功: {name}, 影响行数: {affected_rows}")
                return {
                    "success": True,
                    "message": "海峡数据存储成功",
                    "affected_rows": affected_rows,
                    "strait_name": name
                }
                
        except SQLAlchemyError as e:
            logger.error(f"❌ 数据库存储失败: {e}")
            return {
                "success": False,
                "message": f"数据库存储失败: {str(e)}",
                "affected_rows": 0,
                "strait_name": name
            }
        except Exception as e:
            logger.error(f"❌ 存储执行失败: {e}")
            return {
                "success": False,
                "message": f"存储执行失败: {str(e)}",
                "affected_rows": 0,
                "strait_name": name
            }

    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("🔚 数据库连接已关闭")

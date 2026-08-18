from datetime import datetime
import os
import psycopg2
from loguru import logger
from psycopg2.extras import DictCursor, Json
from psycopg2.pool import ThreadedConnectionPool
import configparser
import uuid

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'config.ini'))

psycopg2.extras.register_uuid()

class JobStore:
    def __init__(self):
        config_info = {
            "user": config['Postgres']['username'],
            "password": config['Postgres']['password'],
            "host": config['Postgres']['host'],
            "port": config['Postgres']['port'],
            "database": config['Postgres']['database']
        }
        self.connection_settings = config_info
        self.connection_pool = None
        self.connect()

    def connect(self):
        try:
            self.connection_pool = ThreadedConnectionPool(
                1, 5, **self.connection_settings
            )
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f"Error while connecting to datastore: {error}")
            raise Exception("Error while connecting to datastore")

    def get_connection(self):
        try:
            conn = self.connection_pool.getconn()
            conn.set_session(autocommit=True)
            return conn
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Not able to get a connection to datastore: {error}")
            raise Exception("Error in getting connection...")

    def put_connection(self, conn):
        try:
            self.connection_pool.putconn(conn)
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Unable to put back the connection in the pool: {error}")
            raise Exception("Error in putting connection...")

    def save_store_map_details(self, st_details):
        query = (
            """INSERT INTO public.store_maps
                (section_id, location_id, floor_id, section_name, coordinates, create_ts)
                VALUES(%s, %s, %s, %s, %s, %s)"""
        )
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, [uuid.uuid4(), st_details["location_id"], st_details["floor_id"],
                                       st_details["section_name"], st_details["coordinates"], datetime.now()])
                asset_result = cursor.rowcount
                if asset_result == 1:
                    return True

        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while store map info at datastore: {error}")
            return False
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while saving store map info at datastore: {error}")
            return False
        finally:
            if conn is not None:
                self.put_connection(conn)

    def save_store_map_details_v2(self, st_details):
        query = (
            """INSERT INTO public.store_maps_info
                (id, location_id, camera_friendly_name, section_info, create_ts)
                VALUES(%s, %s, %s, %s, %s)"""
        )
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, [uuid.uuid4(), st_details["location_id"], st_details["camera_name"],
                                       Json(st_details["section_info"]), datetime.now()])
                asset_result = cursor.rowcount
                if asset_result == 1:
                    return True

        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while store map info v2 at datastore: {error}")
            return False
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while saving store map info v2 at datastore: {error}")
            return False
        finally:
            if conn is not None:
                self.put_connection(conn)                

    def update_camera_friendly_name(self, section_id, camera_friendly_name):
        query = (
            """UPDATE public.store_maps
                SET camera_friendly_name = %s
                WHERE section_id = %s"""
        )
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, [camera_friendly_name, section_id])
                return cursor.rowcount == 1
        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while updating camera_friendly_name at datastore: {error}")
            return False
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while updating camera_friendly_name at datastore: {error}")
            return False
        finally:
            if conn is not None:
                self.put_connection(conn)

    def get_all_by_location_id(self, location_id):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                query = (
                    # """SELECT section_id, location_id, floor_id, section_name,
                    #           coordinates, camera_friendly_name, create_ts
                    #    FROM public.store_maps
                    #    WHERE location_id = %s
                    #    ORDER BY floor_id, section_name;
                    """SELECT
                    sm.id as section_id,
                    sm.location_id,
                    (si->>'floor_id')::INT AS floor_id,
                    si->>'section_name' AS section_name,
                    si->>'coordinates' AS coordinates,
                    sm.camera_friendly_name,
                    sm.create_ts
                FROM public.store_maps_info sm,
                    jsonb_array_elements(sm.section_info) AS si
                WHERE sm.location_id =  %s
                ORDER BY floor_id, section_name;
                    """
                )
                cursor.execute(query, [location_id])
                result = cursor.fetchall()
            return [dict(row) for row in result] if result else []
        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while fetching store maps for location_id {location_id}: {error}")
            return []
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while fetching store maps for location_id {location_id}: {error}")
            return []
        finally:
            if conn is not None:
                self.put_connection(conn)


    def get_all_by_location_id_v2(self, location_id):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                query = (
                    """SELECT section_id, location_id, floor_id, section_name,
                              coordinates, camera_friendly_name, position_lcl_ts, coverage_points,  create_ts
                       FROM public.store_maps_v2
                       WHERE location_id = %s
                       ORDER BY floor_id, section_name;
                    """
                )
                cursor.execute(query, [location_id])
                result = cursor.fetchall()
            return [dict(row) for row in result] if result else []
        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while fetching store maps for location_id {location_id}: {error}")
            return []
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while fetching store maps for location_id {location_id}: {error}")
            return []
        finally:
            if conn is not None:
                self.put_connection(conn)


    def get_section_proximity(self, location_id, x, y):     
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=DictCursor) as cursor:

                query = (
                    """SELECT *
                        FROM public.store_maps
                        WHERE lower(location_id) = lower(%s)
                        ORDER BY coordinates <-> POINT(%s,%s) LIMIT 1;
                    """
                    )
                cursor.execute(query, [location_id, x, y])

                job_result = cursor.fetchall()

            if job_result is None:
                job_result = {}

            return job_result

        except psycopg2.InterfaceError as error:
            logger.error(f"InterfaceError while fetching the section proximity stats info at datastore: {error}")
            return False
        except (Exception, psycopg2.Error) as error:
            logger.error(f"Error while fetching the section proximity info at datastore: {error}")
            return False
        finally:
            if conn is not None:
                self.put_connection(conn)         
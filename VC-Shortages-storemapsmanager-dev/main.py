from datetime import datetime
# from distutils.command.config import config
import uvicorn
from typing import Optional
from fastapi import Request
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from utils.auth import authenticate, app_authorization, RBAC
from utils.auth import APP_RBAC
from utils.utility import delete_video
from service.store_map_service import JobService
from utils.camera_details import fetch_cameras, fetch_section_by_camera, fetch_section_by_camera_v2

from contextlib import asynccontextmanager
import wget
import configparser

from pathlib import Path
from starlette.background import BackgroundTask
import json

config = configparser.ConfigParser()

config.read('./config/config.ini')

CERT_PATH = config["application"]["ssl_cafile"]

responses = {
    400: {"description": "Bad Request"},
    500: {"description": "Internal Server Error"},
}

job_service = JobService()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Store Maps Service OpenAPI schema : V1",
        version="1.0.0",
        description="Bulk Video Job Status Manager OpenAPI schema : V1",
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


        
def auth_dependency(authorization: str = Header(None)):
    pass
#     if authorization is None:
#         raise HTTPException(status_code=400, detail="Authorization header is missing")
#     else:
#         return authenticate(authorization)

@asynccontextmanager
async def lifespan(app: FastAPI):
    job_service.job_store.connect()
    # thread = threading.Thread(target=run_scheduler)
    # thread.start()

    # stores_list = ["T2193", "T0026","T0061","T0068","T0278","T0351","T0531","T0622","T0632","T0804","T0863","T0896","T0945","T1060","T1201","T1251","T1466","T1484","T1783","T1788","T1789","T1792","T1831","T1895","T1946","T1976","T2023","T2113","T2193","T2206","T2218","T2223","T2229","T2346","T2456","T2473","T2586","T2820","T2897","T2904","T2918","T0184","T0188","T0189","T0190","T0192","T0203","T0227","T0229","T0293","T0302","T0311","T0336","T0362","T0627","T0737","T0884","T0910","T0936","T0937","T0996","T0997","T1027","T1100","T1122","T1140","T1209","T1304","T1328","T1340","T1362","T1411","T1424","T1425","T1438","T1472","T1502","T1816","T1819","T1846","T1869","T1883","T2026","T2083","T2096","T2140","T2227","T2280","T2328","T2470","T2482","T2524","T2581","T2584","T2730","T2813","T2892","T2915","T2916","T3319","T3406","T3446","T3451","T0075","T0146","T0219","T0254","T0689","T0758","T0778","T0882","T0887","T0888","T0898","T0955","T0968","T1051","T1061","T1078","T1197","T1336","T1337","T1359","T1376","T1377","T1396","T1459","T1480","T1499","T1512","T1514","T1535","T1760","T1761","T1765","T1766","T1770","T1786","T1795","T1870","T1877","T1918","T1921","T1922","T1932","T1937","T1975","T1981","T2008","T2042","T2055","T2065","T2074","T2142","T2174","T2205","T2244","T2283","T2301","T2320","T2342","T2355","T2370","T2419","T2425","T2426","T2427","T2476","T2489","T2516","T2754","T2865","T2868","T2873","T2882","T2884","T2887","T2919","T2927","T2934","T3375","T3420","T1006","T1007","T1010","T1045","T1088","T1146","T1155","T1157","T1183","T1194","T1218","T1229","T1233","T1330","T1358","T1544","T1808","T1856","T1874","T1942","T2024","T2201","T2247","T2324","T2434","T2537","T2538","T2764","T2880","T2890","T2938","T3356"]
    # print(len(stores_list))

    #save start

     # for location_id in stores_list:
    # location_id = 'T2193'
    # location_no = location_id[1:]
    # store_map_info = job_service.get_map_rendering_details(location_no)

    # floors = store_map_info["floor_details"]

    # location_lookup = {}

    # location_lookup[location_id] = {}

    # save_response = {}

    # save_response["location_id"] = location_id

    # for floor in floors:

    #     floor_id = floor["floor_id"]

    #     map_markers = floor["map_markers"]

    #     for marker in map_markers:
    #         map_details = {}
    #         map_details["location_id"] = location_id
    #         map_details["floor_id"] = floor_id
    #         map_details["section_name"] = marker["text"]
    #         map_details["coordinates"] = f"({marker['coordinates']['x']},{marker['coordinates']['y']})"

    #         location_lookup[location_id][map_details["section_name"]] = {
    #         "floor_id": floor_id,
    #         "coordinates": map_details["coordinates"],
    #     }

    # cameras = fetch_cameras(location_no)

    # for camera in cameras:
    #     camera_response = fetch_section_by_camera_v2(location_id, camera["friendly_name"])
    #     results = camera_response.get("results")

    #     save_response["camera_name"] = camera["friendly_name"]

    #     top_sections = []

    #     if results:
    #         for section in results:
                
    #             section_name = section["section_name"]

    #             section_info = location_lookup.get(location_id, {}).get(section_name)
    #             if section_info:
    #                 coordinates = section_info["coordinates"]
    #                 floor_id = section_info["floor_id"]
    #                 top_sections.append({
    #                     "section_name": section_name,
    #                     "coordinates": coordinates,
    #                     "floor_id": floor_id,
    #                 })

    #         save_response["section_info"] = top_sections

    #         job_service.job_store.save_store_map_details_v2(save_response)

            #save end



    # for location_id in stores_list:
    #     # location_id = 'T2193'
    #     location_no = location_id[1:]
    #     store_map_info = job_service.get_map_rendering_details(location_no)

    #     floors = store_map_info["floor_details"]

    #     for floor in floors:

    #         floor_id = floor["floor_id"]

    #         map_markers = floor["map_markers"]

    #         for marker in map_markers:
    #             map_details = {}
    #             map_details["location_id"] = location_id
    #             map_details["floor_id"] = floor_id
    #             map_details["section_name"] = marker["text"]
    #             map_details["coordinates"] = f"({marker['coordinates']['x']},{marker['coordinates']['y']})"

    #             job_service.job_store.save_store_map_details(map_details)
    yield
    
    job_service.job_store.connection_pool.closeall()
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.openapi = custom_openapi

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"Raised HTTP exception: {repr(exc)}")
    return JSONResponse(
        status_code=exc.status_code, content=jsonable_encoder({"detail": exc.detail})
    )

@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    logger.error(f"Bad request: {str(exc)}")
    return JSONResponse(
        status_code=400, content=jsonable_encoder({"detail": exc.errors()})
    )

@app.get("/store_maps/v1")
def default():
    return {"msg": "Store Maps service"}

@app.get("/health")
def health():
    return {"Status": "Ok"}

@app.get(
    "/store_maps/v1/location/{location_id}",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_all_by_location_id(location_id: str):
    result = job_service.get_all_by_location_id(location_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No store map data found for location_id: {location_id}")
    return JSONResponse(status_code=200, content=jsonable_encoder(result))

@app.get(
    "/store_maps/v1/section/{location_id}",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_map_rendering_details(location_id: str):
    location_no = location_id[1:]
    store_map_info = job_service.get_map_rendering_details(location_no)

    floors = store_map_info["floor_details"]

    location_details = []

    for floor in floors:

        floor_id = floor["floor_id"]

        map_markers = floor["map_markers"]

        for marker in map_markers:
            map_details = {}
            map_details["location_id"] = location_id
            map_details["floor_id"] = floor_id
            map_details["section_name"] = marker["text"]
            map_details["coordinates"] = f"({marker['coordinates']['x']},{marker['coordinates']['y']})"
            location_details.append(map_details)
    
    return JSONResponse(status_code=200, content=jsonable_encoder(location_details))

@app.get(
    "/store_maps/v2/location/{location_id}",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_all_by_location_id_v2(location_id: str):
    result = job_service.get_all_by_location_id_v2(location_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"No store map data found for location_id: {location_id}")
    return JSONResponse(status_code=200, content=jsonable_encoder(result))


@app.get(
    "/store_maps/v1/proximity",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
async def get_section_proximity(location_id: str, x: float, y: float):
    result = await job_service.get_section_proximity(location_id, x, y)

    # paginated_data = pagination(result, int(store_data.get('page', 1)), int(store_data.get('items_per_page', 10)))
    return JSONResponse(status_code=200, content=jsonable_encoder(result))


@app.get(
    "/store_maps/v1/map_rendering_details",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_map_rendering_details(location_id: str):
    result = job_service.get_map_rendering_details(location_id)

    # paginated_data = pagination(result, int(store_data.get('page', 1)), int(store_data.get('items_per_page', 10)))
    return JSONResponse(status_code=200, content=jsonable_encoder(result))

@app.get(
    "/store_shapes/v1/map_rendering_details",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_store_shapes(location_id: str, floor_id: str, section: str):
    result = job_service.get_store_shapes(location_id, floor_id, section)

    # paginated_data = pagination(result, int(store_data.get('page', 1)), int(store_data.get('items_per_page', 10)))
    return JSONResponse(status_code=200, content=jsonable_encoder(result))

@app.get(
    "/store_maps/v1/svg_image",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_section_proximity(location_id: str, floor_id: str):
    result = job_service.get_store_maps(location_id, floor_id)

    return Response(
            content=result,
            media_type="image/svg+xml",
        )

@app.get(
    "/store_maps/v1/camera_proximity",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
def get_all_by_location_id(location_id: str):
    result = job_service.get_all_by_location_id(location_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No store map data found for location_id: {location_id}")
    return JSONResponse(status_code=200, content=jsonable_encoder(result))

@app.post(
    "/store_maps/v1/demography",
    status_code=200,
    responses={
        200: {"description": "OK"},
        404: {"description": "Not Found"},
        **responses
    },
)
async def save_request(request: Request):
    """
    :param store_data: {
                "start_datetime": "2026-05-10 00:00:00",
                "end_datetime": "2026-05-10 23:59:00",
                "store_numbers": ["T2193"],
                "page_number": 0
            }
    """
    request_info = await request.json()
   
    result = await job_service.get_store_demography(request_info)

    # paginated_data = pagination(result, int(store_data.get('page', 1)), int(store_data.get('items_per_page', 10)))
    return JSONResponse(status_code=200, content=jsonable_encoder(result))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        port=6000,
        host="0.0.0.0",
        workers=1,
        reload=False,
        log_level="info",
        access_log=False,
        limit_concurrency=int(config["application"]["max_concurrent_limit"]),
    )
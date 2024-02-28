import datetime
from typing import Literal

from pydantic import BaseModel


class UserIdentity(BaseModel):
    principalId: str


class BucketInfo(BaseModel):
    name: str
    ownerIdentity: UserIdentity


class ObjectInfo(BaseModel):
    key: str
    size: int
    eTag: str
    sequencer: str


class S3Event(BaseModel):
    s3SchemaVersion: Literal["1.0"]
    configurationId: str
    bucket: BucketInfo
    object: ObjectInfo


class AWSRecord(BaseModel):
    eventVersion: Literal["2.0", "2.2"]
    eventTime: datetime.datetime
    eventName: str
    userIdentity: UserIdentity
    s3: S3Event


class AWSEvent(BaseModel):
    Records: list[AWSRecord]

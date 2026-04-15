"""Fixtures for all tests.
"""
from flask import Flask
from pytest import fixture


@fixture
def app():
    """A basic app instance.
    """
    instance = Flask(__name__)
    return instance

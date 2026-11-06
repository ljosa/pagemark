"""Narrow corrections for the pinned Cocoa bridge metadata."""
import objc


def configure_document_open_callback():
    # pyobjc-framework-Cocoa 12.1 describes this block as taking one object.
    # AppKit passes (NSDocument *, BOOL, NSError *). Without this correction,
    # PyObjC raises BadPrototypeError before calling the native open method.
    # Apply after importing AppKit, without modifying the installed package.
    # https://developer.apple.com/documentation/appkit/nsdocumentcontroller/opendocument(withcontentsof:display:completionhandler:)
    objc.registerMetaDataForSelector(
        b"NSDocumentController",
        b"openDocumentWithContentsOfURL:display:completionHandler:",
        {"arguments": {4: {"callable": {
            "retval": {"type": b"v"},
            "arguments": {
                0: {"type": b"^v"},  # The block itself, hidden from Python.
                1: {"type": b"@"},
                2: {"type": objc._C_NSBOOL},
                3: {"type": b"@"},
            },
        }}}},
    )

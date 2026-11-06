"""Native document opening and replacement of the untouched startup document."""
import AppKit as A
import objc

from .cocoa_compat import configure_document_open_callback

configure_document_open_callback()


def is_replaceable_startup_document(document):
    return (
        getattr(document, "transient_startup", False)
        and document.fileURL() is None
        and not document.isDocumentEdited()
        and not document.session.value.text
        and not (document.editor and document.editor.hasMarkedText())
    )


class PagemarkDocumentController(A.NSDocumentController):
    def openDocumentWithContentsOfURL_display_completionHandler_(self, url, display, completion):
        candidates = tuple(document for document in self.documents()
                           if display and is_replaceable_startup_document(document))

        def completed(document, already_open, error):
            if document is not None and error is None:
                for candidate in candidates:
                    # Opening can finish asynchronously. Recheck both ownership
                    # and edits so concurrent opens or typing cannot discard work.
                    if (candidate != document and candidate in self.documents()
                            and is_replaceable_startup_document(candidate)):
                        candidate.transient_startup = False
                        candidate.close()
            if completion is not None:
                completion(document, already_open, error)

        objc.super(PagemarkDocumentController, self).\
            openDocumentWithContentsOfURL_display_completionHandler_(url, display, completed)

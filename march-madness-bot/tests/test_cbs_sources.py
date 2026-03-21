import pytest
from unittest.mock import AsyncMock, patch
from cbs import detect_site, _extract_cbs

def test_detect_site_cbs():
    assert detect_site("https://www.cbssports.com") == "cbs"
    assert detect_site("https://cbssports.com") == "cbs"
    assert detect_site("https://picks.cbssports.com") == "cbs"
    assert detect_site("https://www.espn.com") == "espn"
    assert detect_site("https://www.yahoo.com") == "yahoo"
    assert detect_site("https://unknown.com") == "unknown"
    assert detect_site("") == "unknown"
    assert detect_site(None) == "unknown"

@patch('cbs.requests.get')
@pytest.mark.asyncio
async def test_extract_cbs(mock_get):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = """
    <table>
        <tbody>
            <tr><td>1</td><td>Champion</td><td>Bracket Name</td><td>100</td></tr>
            <tr><td>2</td><td>Runner Up</td><td>Another Bracket</td><td>90</td></tr>
        </tbody>
    </table>
    """
    mock_get.return_value = mock_response

    async with AsyncMock() as page:
        await page.query_selector_all.return_value = [AsyncMock(), AsyncMock()]
        await page.query_selector_all.return_value[0].query_selector_all.return_value = [AsyncMock(), AsyncMock(), AsyncMock()]
        await page.query_selector_all.return_value[0].query_selector_all.return_value[0].inner_text.return_value = "1"
        await page.query_selector_all.return_value[0].query_selector_all.return_value[1].inner_text.return_value = "Champion"
        await page.query_selector_all.return_value[0].query_selector_all.return_value[2].inner_text.return_value = "Bracket Name"
        await page.query_selector_all.return_value[0].query_selector_all.return_value[3].inner_text.return_value = "100"
        
        result = await _extract_cbs(page, 5)
        assert result == [(1, "Champion", 100), (2, "Runner Up", 90)]

@patch('cbs.requests.get')
@pytest.mark.asyncio
async def test_extract_cbs_no_data(mock_get):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<table><tbody></tbody></table>"
    mock_get.return_value = mock_response

    async with AsyncMock() as page:
        await page.query_selector_all.return_value = []
        result = await _extract_cbs(page, 5)
        assert result == []
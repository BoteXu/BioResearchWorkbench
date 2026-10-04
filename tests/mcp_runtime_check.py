"""Actual DuckDB security/QC checks in the optional environment; core stays lightweight."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_mcp_integrations import IntegrationChecks,query
import unittest


class ActualQueryChecks(IntegrationChecks):
    def test_actual_table_query_and_external_view_refused(self):
        import duckdb
        path=self.root/'selected.duckdb';conn=duckdb.connect(str(path))
        conn.execute('CREATE TABLE observations AS SELECT 1 AS id, 2 AS value UNION ALL SELECT 2, 4')
        private=self.root/'private.csv';private.write_text('id\n3\n')
        conn.execute("CREATE VIEW external_view AS SELECT * FROM read_csv('"+str(private).replace("'","''")+"')")
        conn.close()
        r=query.query_selected_table(str(path),'observations',['id','value'],[{'column':'id','op':'=','value':2}]);self.assertEqual(r['records'],[{'id':2,'value':4}]);self.assertFalse(r['truncated'])
        with self.assertRaises(ValueError):query.query_selected_table(str(path),'observations; DROP TABLE observations',['id'])
        with self.assertRaises(ValueError):query.query_selected_table(str(path),'observations',['id'],[{'column':'id','op':'=','value':[]}])
        with self.assertRaises(duckdb.Error):query.query_selected_table(str(path),'external_view',['id'])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ActualQueryChecks)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

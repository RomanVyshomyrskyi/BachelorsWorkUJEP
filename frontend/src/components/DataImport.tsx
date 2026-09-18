/**
 * @module components/DataImport
 * @description Data import wizard for CSV/Excel files into database tables via Superset.
 * Supports multi-step process: File Upload → Select Superset → Select Database → Select Schema → Select Table → Map Columns & Import.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import type {
  SupersetServer,
  SupersetDb,
  DbTable,
  DbColumn,
  ColumnMapping,
  BatchInsertResult,
  FileData,
  ImportWizardStep,
} from '../types';
import { api } from '../api/service';

function DataImport() {
  const [step, setStep] = useState<ImportWizardStep>(1);
  const [supersetServers, setSupersetServers] = useState<SupersetServer[]>([]);
  const [selectedServerId, setSelectedServerId] = useState<string>('');
  const [databases, setDatabases] = useState<SupersetDb[]>([]);
  const [selectedDbId, setSelectedDbId] = useState<number | null>(null);
  const [schemas, setSchemas] = useState<string[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<string>('');
  const [tables, setTables] = useState<DbTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [tableColumns, setTableColumns] = useState<DbColumn[]>([]);
  const [fileData, setFileData] = useState<FileData | null>(null);
  const [fileName, setFileName] = useState<string>('');
  const [fileError, setFileError] = useState<string>('');
  const [columnMappings, setColumnMappings] = useState<ColumnMapping[]>([]);
  const [batchSize, setBatchSize] = useState<number>(50);
  const [importResult, setImportResult] = useState<BatchInsertResult | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [loading, setLoading] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedTableSchema, setSelectedTableSchema] = useState<string>('');

  useEffect(() => {
    loadSupersetServers();
  }, []);

  useEffect(() => {
    console.log('[DataImport] Schemas state:', schemas, 'selectedSchema:', selectedSchema);
  }, [schemas, selectedSchema]);

  const loadSupersetServers = async () => {
    setLoading('servers');
    try {
      const servers = await api.listSupersetServers();
      setSupersetServers(servers);
    } catch (error) {
      console.error('Failed to load Superset servers:', error);
      setFileError('Failed to load Superset servers');
    } finally {
      setLoading('');
    }
  };

  const handleServerSelect = async (serverId: string) => {
    setSelectedServerId(serverId);
    setSelectedDbId(null);
    setSelectedSchema('');
    setSelectedTable('');
    setDatabases([]);
    setTables([]);
    setTableColumns([]);
    if (!serverId) return;
    setLoading('databases');
    try {
      const dbs = await api.listSupersetDatabases(serverId);
      setDatabases(dbs);
    } catch (error) {
      console.error('Failed to load databases:', error);
      setFileError('Failed to load databases');
    } finally {
      setLoading('');
    }
  };

  const handleDbSelect = async (dbId: number) => {
    setSelectedDbId(dbId);
    setSelectedSchema('');
    setSelectedTable('');
    setTables([]);
    setTableColumns([]);
    setSchemas([]);
    if (!dbId) return;
    setLoading('schema');
    try {
      const db = databases.find(d => d.id === dbId);
      const schema = db?.backend === 'postgresql' ? 'public' : undefined;
      console.log('[DataImport] Calling getSupersetDatabaseSchema with:', { serverId: selectedServerId, dbId, schema });
      const schemaData = await api.getSupersetDatabaseSchema(selectedServerId, dbId, schema);
      console.log('[DataImport] getSupersetDatabaseSchema result:', JSON.stringify(schemaData, null, 2).substring(0, 500));
      console.log('[DataImport] schemaData.tables:', schemaData?.tables?.length);
      if (schemaData && schemaData.tables && schemaData.tables.length > 0) {
        const schemaName = schema || (db?.backend === 'mssql' ? 'dbo' : '');
        setSchemas([schemaName]);
        const dbTables = schemaData.tables.map((t: any) => ({
          name: t.table_name,
          schema: schemaName,
          table_rows: 0,
          column_count: t.columns?.length || 0,
        }));
        setTables(dbTables);
        console.log('[DataImport] Tables set:', dbTables.length);
      } else {
        console.warn('[DataImport] No tables found in response');
      }
    } catch (error) {
      console.error('Failed to load schema:', error);
      setFileError('Failed to load schema');
    } finally {
      setLoading('');
    }
  };

  const handleTableSelect = async (tableName: string) => {
    setSelectedTable(tableName);
    if (!tableName || !selectedDbId) return;
    setLoading('columns');
    try {
      const tbl = tables.find(t => t.name === tableName);
      if (tbl) setSelectedTableSchema(tbl.schema);
      const schemaData = await api.getSupersetDatabaseSchema(selectedServerId, selectedDbId, selectedTableSchema);
      const tableInfo = schemaData?.tables?.find((t: any) => t.table_name === tableName);
      if (tableInfo?.columns) {
        const cols: DbColumn[] = tableInfo.columns.map((col: any) => ({
          name: col.column_name || col.COLUMN_NAME || col.name,
          type: col.data_type || col.DATA_TYPE || col.type || 'UNKNOWN',
          nullable: col.is_nullable === 'YES' || col.IS_NULLABLE === 'YES' || col.nullable !== false,
          is_primary_key: false,
          max_length: null,
        }));
        setTableColumns(cols);
        
        if (fileData && fileData.headers.length > 0) {
          const dbColNames = cols.map(c => c.name.toLowerCase());
          const newMappings: ColumnMapping[] = fileData.headers.map(header => {
            const idx = dbColNames.indexOf(header.toLowerCase());
            return {
              fileColumn: header,
              dbColumn: idx >= 0 && cols[idx] ? cols[idx].name : '__skip__',
            };
          });
          setColumnMappings(newMappings);
        }
      }
      setImportResult(null);
    } catch (error) {
      console.error('Failed to load columns:', error);
      setFileError('Failed to load columns');
    } finally {
      setLoading('');
    }
  };

  const handleFileUpload = useCallback((file: File) => {
    setFileError('');
    setFileName(file.name);
    setFileData(null);
    setColumnMappings([]);
    setImportResult(null);

    const ext = file.name.split('.').pop()?.toLowerCase();

    if (ext === 'csv') {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (results.errors.length > 0) {
            setFileError(`CSV parse errors: ${results.errors.length} error(s)`);
            return;
          }
          const headers = results.meta.fields || [];
          const rows = results.data.map((row: any) => headers.map(h => row[h] ?? ''));
          setFileData({ headers, rows });
        },
        error: (err) => {
          setFileError(`CSV parse error: ${err.message}`);
        },
      });
    } else if (ext === 'xlsx' || ext === 'xls') {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target?.result as ArrayBuffer);
          const workbook = XLSX.read(data, { type: 'array' });
          const sheetName = workbook.SheetNames[0];
          if (!sheetName) {
            setFileError('No sheets found in Excel file');
            return;
          }
          const sheet = workbook.Sheets[sheetName];
          if (!sheet) {
            setFileError('Sheet not found in Excel file');
            return;
          }
          const json = XLSX.utils.sheet_to_json<any>(sheet, { defval: '' });
          const headers = Object.keys(json.length > 0 ? json[0] : {});
          const rows = json.map(row => headers.map(h => row[h] ?? ''));
          setFileData({ headers, rows });
        } catch (err: any) {
          setFileError(`Excel parse error: ${err.message}`);
        }
      };
      reader.readAsArrayBuffer(file);
    } else {
      setFileError('Unsupported file format. Please use .csv, .xlsx, or .xls');
    }
  }, []);

  const initializeMappings = () => {
    if (!fileData || tableColumns.length === 0) return;
    const mappings: ColumnMapping[] = fileData.headers.map(header => ({
      fileColumn: header,
      dbColumn: '__skip__',
    }));
    setColumnMappings(mappings);
  };

  const updateMapping = (fileColumn: string, dbColumn: string) => {
    setColumnMappings(prev =>
      prev.map(m => m.fileColumn === fileColumn ? { ...m, dbColumn } : m),
    );
  };

  const nextStep = () => {
    if (step === 2 && !selectedServerId) return;
    if (step === 3 && !selectedDbId) return;
    if (step === 4 && !selectedSchema) return;
    if (step === 5 && !selectedTable) return;
    if (step === 5) {
      initializeMappings();
    }
    if (step < 6) setStep((step + 1) as ImportWizardStep);
  };

  const prevStep = () => {
    if (step > 1) setStep((step - 1) as ImportWizardStep);
  };

  const executeImport = async () => {
    if (!fileData || columnMappings.length === 0 || !selectedTable) return;
    setImportLoading(true);
    try {
      const mappedColumns = columnMappings
        .filter(m => m.dbColumn !== '__skip__')
        .map(m => m.dbColumn);

      const mappedRows = fileData.rows.map(row => {
        const obj: Record<string, any> = {};
        columnMappings
          .filter(m => m.dbColumn !== '__skip__')
          .forEach(m => {
            const idx = fileData!.headers.indexOf(m.fileColumn);
            obj[m.dbColumn] = idx >= 0 ? row[idx] : '';
          });
        return obj;
      });

      const result = await api.supersetBatchInsertRows(
        selectedServerId,
        selectedDbId!,
        selectedTable,
        mappedColumns,
        mappedRows,
        batchSize,
        selectedTableSchema || undefined,
      );
      setImportResult(result);
    } catch (error: any) {
      console.error('Import failed:', error);
      setImportResult({
        success: false,
        total_rows: fileData.rows.length,
        inserted_rows: 0,
        failed_rows: fileData.rows.length,
        batches: [],
        errors: [error.message || 'Import failed'],
      });
    } finally {
      setImportLoading(false);
    }
  };

  const resetWizard = () => {
    setStep(1);
    setSelectedServerId('');
    setSelectedDbId(null);
    setSelectedSchema('');
    setSelectedTable('');
    setDatabases([]);
    setTables([]);
    setTableColumns([]);
    setFileData(null);
    setFileName('');
    setFileError('');
    setColumnMappings([]);
    setImportResult(null);
    setBatchSize(50);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const mappedCount = columnMappings.filter(m => m.dbColumn !== '__skip__').length;
  const stepTitles = ['Upload File', 'Select Superset', 'Select Database', 'Select Schema', 'Select Table', 'Map & Import'];

  return (
    <div>
      <h1 className="page-title">Data Import</h1>

      <div className="wizard-progress" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {stepTitles.map((title, i) => {
          const stepNum = (i + 1) as ImportWizardStep;
          const isActive = step === stepNum;
          const isDone = step > stepNum;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  background: isDone ? 'var(--success)' : isActive ? 'var(--accent)' : '#e0e0e0',
                  color: isDone || isActive ? 'white' : '#666',
                }}
              >
                {isDone ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: '0.8rem', fontWeight: isActive ? 600 : 400, color: isActive ? 'var(--accent)' : '#666' }}>
                {title}
              </span>
            </div>
          );
        })}
      </div>

      {step === 1 && (
        <div className="card">
          <div className="card-title">Step 1: Upload Your File</div>
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <div
              className="drop-zone"
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: '2px dashed var(--border)',
                borderRadius: '12px',
                padding: '3rem 2rem',
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
            >
              <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📄</div>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
                {fileName ? `Selected: ${fileName}` : 'Click to select a file'}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                Supports CSV, XLSX, XLS files
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(file);
                }}
                style={{ display: 'none' }}
              />
            </div>
            {fileError && (
              <div className="error-message" style={{ color: 'var(--danger)', marginTop: '1rem' }}>
                {fileError}
              </div>
            )}
          </div>

          {fileData && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div style={{ fontWeight: 600 }}>Preview: {fileData.headers.slice(0, 5).join(', ')}{fileData.headers.length > 5 ? '...' : ''}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                  {fileData.rows.length} rows × {fileData.headers.length} columns
                </div>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ background: '#f8f9fa' }}>
                      {fileData.headers.map((h, i) => (
                        <th key={i} style={{ padding: '0.5rem', border: '1px solid var(--border)', textAlign: 'left', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fileData.rows.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j} style={{ padding: '0.4rem 0.5rem', border: '1px solid var(--border)' }}>
                            {String(cell).length > 30 ? String(cell).slice(0, 30) + '...' : cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {fileData.rows.length > 5 && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', textAlign: 'center', marginTop: '0.5rem' }}>
                    Showing 5 of {fileData.rows.length} rows
                  </div>
                )}
              </div>
            </div>
          )}

          {fileData && (
            <div className="actions-row" style={{ justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button className="btn btn-primary" onClick={nextStep} disabled={!fileData}>
                Continue → Select Superset
              </button>
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <div className="card-title">Step 2: Select Superset Instance</div>
          <div className="form-group">
            <label className="form-label">Superset Server</label>
            <select
              className="form-select"
              value={selectedServerId}
              onChange={(e) => handleServerSelect(e.target.value)}
              disabled={importLoading}
            >
              <option value="">Select a Superset instance...</option>
              {supersetServers.map(server => (
                <option key={server.id} value={server.id}>
                  {server.name || server.id} ({server.host}:{server.port})
                </option>
              ))}
            </select>
          </div>
          <div className="actions-row" style={{ justifyContent: 'space-between', marginTop: '1rem' }}>
            <button className="btn btn-outline" onClick={prevStep}>← Back</button>
            <button className="btn btn-primary" onClick={nextStep} disabled={!selectedServerId}>
              Continue → Select Database
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card">
          <div className="card-title">Step 3: Select Database</div>
          <div className="form-group">
            <label className="form-label">Database</label>
            <select
              className="form-select"
              value={selectedDbId || ''}
              onChange={(e) => handleDbSelect(Number(e.target.value))}
              disabled={importLoading}
            >
              <option value="">Select a database...</option>
              {databases.map(db => (
                <option key={db.id} value={db.id}>
                  {db.database_name} ({db.backend})
                </option>
              ))}
            </select>
          </div>
          <div className="actions-row" style={{ justifyContent: 'space-between', marginTop: '1rem' }}>
            <button className="btn btn-outline" onClick={prevStep}>← Back</button>
            <button className="btn btn-primary" onClick={nextStep} disabled={!selectedDbId}>
              Continue → Select Schema
            </button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="card">
          <div className="card-title">Step 4: Select Schema</div>
          <div className="form-group">
            <label className="form-label">Schema</label>
            <select
              className="form-select"
              value={selectedSchema}
              onChange={(e) => setSelectedSchema(e.target.value)}
              disabled={importLoading}
            >
              <option value="">Select a schema...</option>
              {schemas.map(schema => (
                <option key={schema} value={schema}>
                  {schema}
                </option>
              ))}
            </select>
          </div>
          <div className="actions-row" style={{ justifyContent: 'space-between', marginTop: '1rem' }}>
            <button className="btn btn-outline" onClick={prevStep}>← Back</button>
            <button className="btn btn-primary" onClick={nextStep} disabled={!selectedSchema}>
              Continue → Select Table
            </button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="card">
          <div className="card-title">Step 5: Select Table</div>
          <div className="form-group">
            <label className="form-label">Table</label>
            <select
              className="form-select"
              value={selectedTable}
              onChange={(e) => handleTableSelect(e.target.value)}
              disabled={!selectedSchema || importLoading}
            >
              <option value="">Select a table...</option>
              {tables.map(t => (
                <option key={t.name} value={t.name}>
                  {t.name} ({t.column_count} cols)
                </option>
              ))}
            </select>
          </div>
          {selectedTable && tableColumns.length > 0 && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: '#f8f9fa', borderRadius: '8px' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Table columns ({tableColumns.length}):</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {tableColumns.map(col => (
                  <span
                    key={col.name}
                    style={{
                      padding: '0.25rem 0.5rem',
                      background: col.is_primary_key ? 'rgba(52, 152, 219, 0.15)' : 'white',
                      border: '1px solid var(--border)',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                    }}
                  >
                    {col.name} <span style={{ color: 'var(--text-light)' }}>({col.type})</span>
                    {col.is_primary_key && ' 🔑'}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="actions-row" style={{ justifyContent: 'space-between', marginTop: '1rem' }}>
            <button className="btn btn-outline" onClick={prevStep}>← Back</button>
            <button className="btn btn-primary" onClick={nextStep} disabled={!selectedTable || !tableColumns.length}>
              Continue → Map Columns
            </button>
          </div>
        </div>
      )}

      {step === 6 && (
        <div className="card">
          <div className="card-title">Step 6: Map Columns & Import</div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ padding: '0.6rem', border: '1px solid var(--border)', textAlign: 'left', width: '25%' }}>File Column</th>
                  <th style={{ padding: '0.6rem', border: '1px solid var(--border)', textAlign: 'left', width: '50%' }}>→ Target DB Column</th>
                  <th style={{ padding: '0.6rem', border: '1px solid var(--border)', textAlign: 'left', width: '25%' }}>Data Type</th>
                </tr>
              </thead>
              <tbody>
                {(fileData?.headers || []).map((header, i) => {
                  const existing = columnMappings.find(m => m.fileColumn === header);
                  const dbCol = existing?.dbColumn || '__skip__';
                  return (
                    <tr key={i}>
                      <td style={{ padding: '0.5rem', border: '1px solid var(--border)', fontWeight: 500 }}>{header}</td>
                      <td style={{ padding: '0.5rem', border: '1px solid var(--border)' }}>
                        <select
                          className="form-select"
                          value={dbCol}
                          onChange={(e) => updateMapping(header, e.target.value)}
                          disabled={importLoading}
                          style={{ padding: '0.3rem 0.5rem', fontSize: '0.8rem' }}
                        >
                          <option value="__skip__">-- Skip --</option>
                          {tableColumns.map(col => (
                            <option key={col.name} value={col.name}>
                              {col.name} ({col.type})
                              {col.is_primary_key ? ' 🔑' : ''}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td style={{ padding: '0.5rem', border: '1px solid var(--border)', color: 'var(--text-light)', fontSize: '0.8rem' }}>
                        {fileData?.rows[0]?.[i] !== undefined ? typeof fileData.rows[0][i] : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: '0.5rem' }}>
            {mappedCount} of {fileData?.headers.length || 0} columns mapped
          </div>

          <div className="form-group" style={{ marginTop: '1.5rem', maxWidth: '300px' }}>
            <label className="form-label">Batch Size (rows per INSERT)</label>
            <input
              type="number"
              className="form-input"
              value={batchSize}
              onChange={(e) => setBatchSize(Math.max(1, Math.min(200, parseInt(e.target.value) || 50)))}
              min={1}
              max={200}
              disabled={importLoading}
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: '0.25rem' }}>
              Recommended: 50, Max: 200
            </div>
          </div>

          <div className="actions-row" style={{ justifyContent: 'space-between', marginTop: '1.5rem' }}>
            <button className="btn btn-outline" onClick={prevStep}>← Back</button>
            <button
              className="btn btn-success"
              onClick={executeImport}
              disabled={importLoading || mappedCount === 0}
            >
              {importLoading ? 'Importing...' : `Import ${fileData?.rows.length || 0} Rows`}
            </button>
          </div>
        </div>
      )}

      {step === 6 && importResult && (
        <div className="card">
          <div className="card-title">Import Result</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ padding: '1rem', background: importResult.success ? 'rgba(39, 174, 96, 0.1)' : 'rgba(231, 76, 60, 0.1)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: importResult.success ? 'var(--success)' : 'var(--danger)' }}>
                {importResult.inserted_rows}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Inserted</div>
            </div>
            <div style={{ padding: '1rem', background: importResult.failed_rows > 0 ? 'rgba(231, 76, 60, 0.1)' : 'rgba(39, 174, 96, 0.1)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: importResult.failed_rows > 0 ? 'var(--danger)' : 'var(--success)' }}>
                {importResult.failed_rows}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Failed</div>
            </div>
            <div style={{ padding: '1rem', background: '#f8f9fa', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>
                {importResult.batches.length}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>Batches</div>
            </div>
          </div>

          {importResult.batches.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Batch Details:</div>
              {importResult.batches.map((batch, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0.5rem 0.75rem',
                    background: batch.success ? 'rgba(39, 174, 96, 0.05)' : 'rgba(231, 76, 60, 0.05)',
                    borderRadius: '6px',
                    marginBottom: '0.25rem',
                    fontSize: '0.8rem',
                    borderLeft: `3px solid ${batch.success ? 'var(--success)' : 'var(--danger)'}`,
                  }}
                >
                  <span>Batch {batch.batch_number} (rows {batch.start_row}-{batch.end_row})</span>
                  <span style={{ fontWeight: 600, color: batch.success ? 'var(--success)' : 'var(--danger)' }}>
                    {batch.success ? `${batch.rows} rows inserted` : `Failed: ${batch.error}`}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="actions-row" style={{ justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={resetWizard}>Import Another File</button>
          </div>
        </div>
      )}

      {step === 6 && importResult && importResult.success === false && (
        <div style={{ marginTop: '1rem' }}>
          <div className="card" style={{ border: '2px solid var(--danger)' }}>
            <div className="card-title" style={{ color: 'var(--danger)' }}>Import Failed</div>
            {importResult.errors?.map((err, i) => (
              <div key={i} style={{ padding: '0.5rem', background: 'rgba(231, 76, 60, 0.05)', borderRadius: '6px', marginBottom: '0.25rem', fontSize: '0.85rem', color: 'var(--danger)' }}>
                {err}
              </div>
            ))}
            <div className="actions-row" style={{ marginTop: '1rem' }}>
              <button className="btn btn-primary" onClick={resetWizard}>Try Again</button>
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading...</span>
        </div>
      )}
    </div>
  );
}

export default DataImport;

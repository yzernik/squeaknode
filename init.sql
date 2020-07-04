CREATE TABLE IF NOT EXISTS squeak (
  hash CHAR(64) PRIMARY KEY,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  nVersion INTEGER NOT NULL,
  hashEncContent CHAR(64) NOT NULL,
  hashReplySqk CHAR(64) NOT NULL,
  hashBlock CHAR(64) NOT NULL,
  nBlockHeight INTEGER NOT NULL,
  scriptPubKey VARCHAR(100) NOT NULL,
  encryptionKey CHAR(324) NOT NULL,
  encDatakey CHAR(256) NOT NULL,
  vchIv CHAR(32) NOT NULL,
  nTime INTEGER NOT NULL,
  nNonce BIGINT NOT NULL,
  encContent CHAR(2272) NOT NULL,
  scriptSig VARCHAR(400) NOT NULL,
  address VARCHAR(50) NOT NULL,
  vchDecryptionKey VARCHAR(8000),
  content CHAR(1120)
);

CREATE INDEX IF NOT EXISTS idx_squeak_address
  ON squeak(address);
